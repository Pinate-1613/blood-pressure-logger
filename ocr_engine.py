import cv2
import numpy as np
import os
from datetime import datetime

class BPOcrEngine:
    def __init__(self):
        # Generate digit templates at runtime for matching
        self.templates = {}
        self.generate_templates()

    def generate_templates(self):
        """
        Generates standard binary templates for digits 0-9.
        We draw both standard sans-serif and 7-segment style digits to cover various monitor displays.
        Each template is resized to 20x30 pixels.
        """
        digits = "0123456789"
        
        # 1. Standard sans-serif font templates
        for d in digits:
            img = np.zeros((60, 40), dtype=np.uint8)
            cv2.putText(img, d, (5, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.8, 255, 6, cv2.LINE_AA)
            # Threshold to make it strictly binary
            _, thresh = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)
            # Find bounding box to crop tightly
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                x, y, w, h = cv2.boundingRect(contours[0])
                for c in contours[1:]:
                    x2, y2, w2, h2 = cv2.boundingRect(c)
                    x = min(x, x2)
                    y = min(y, y2)
                    w = max(x + w, x2 + w2) - x
                    h = max(y + h, y2 + h2) - y
                cropped = thresh[y:y+h, x:x+w]
                resized = cv2.resize(cropped, (20, 30))
                self.templates[f"sans_{d}"] = resized

        # 2. 7-segment style programmatically drawn templates
        # We define a 7-segment display grid and activate specific segments for each digit
        seg_coords = {
            'a': [(2, 0), (18, 0)],   # Top
            'b': [(19, 1), (19, 14)], # Top-right
            'c': [(19, 16), (19, 29)],# Bottom-right
            'd': [(2, 29), (18, 29)], # Bottom
            'e': [(0, 16), (0, 29)],  # Bottom-left
            'f': [(0, 1), (0, 14)],   # Top-left
            'g': [(2, 15), (18, 15)], # Middle
        }
        
        digit_segs = {
            '0': ['a', 'b', 'c', 'd', 'e', 'f'],
            '1': ['b', 'c'],
            '2': ['a', 'b', 'g', 'e', 'd'],
            '3': ['a', 'b', 'g', 'c', 'd'],
            '4': ['f', 'b', 'g', 'c'],
            '5': ['a', 'f', 'g', 'c', 'd'],
            '6': ['a', 'f', 'e', 'd', 'c', 'g'],
            '7': ['a', 'b', 'c'],
            '8': ['a', 'b', 'c', 'd', 'e', 'f', 'g'],
            '9': ['a', 'b', 'c', 'd', 'f', 'g']
        }

        for d, segments in digit_segs.items():
            img = np.zeros((30, 20), dtype=np.uint8)
            for seg in segments:
                p1, p2 = seg_coords[seg]
                # Draw thick segments
                cv2.line(img, p1, p2, 255, 3)
            self.templates[f"seg_{d}"] = img

    def preprocess_image(self, img_path):
        """
        Preprocesses the monitor display image to facilitate digit segmentation.
        """
        # Load image
        img = cv2.imread(img_path)
        if img is None:
            raise ValueError(f"Could not load image at path: {img_path}")

        # Resize to standard width to keep threshold/contour parameters consistent
        h, w = img.shape[:2]
        new_w = 600
        new_h = int(h * (new_w / w))
        img_resized = cv2.resize(img, (new_w, new_h))

        # Convert to Grayscale
        gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)

        # Apply CLAHE to enhance contrast of LCD segments against background
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        contrast = clahe.apply(gray)

        # Apply Adaptive Thresholding
        # Digital screens can have uneven illumination, so adaptive thresholding is critical
        thresh = cv2.adaptiveThreshold(
            contrast, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 51, 15
        )

        # Morphological operations to clean up digits
        # 7-segment lines can be disconnected, so we apply a small closing
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 4))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 2)))

        return img_resized, cleaned

    def segment_digits(self, binary_img):
        """
        Locates and segments digit-like contours from the preprocessed binary image.
        Returns a list of bounding boxes: (x, y, w, h).
        """
        contours, _ = cv2.findContours(binary_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        digit_boxes = []
        img_h, img_w = binary_img.shape

        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            
            # Aspect ratio filtering: digits are taller than they are wide
            aspect_ratio = w / h
            
            # Constraints:
            # - Digit height should be between 3% and 35% of the total screen height
            # - Aspect ratio should be roughly 0.2 to 0.95 (excluding decimal points/small noise)
            # - Minimum width and height to filter out stray noise
            if 0.15 < aspect_ratio < 0.95 and (img_h * 0.04) < h < (img_h * 0.35) and w > 6 and h > 15:
                digit_boxes.append((x, y, w, h))

        # Remove overlapping/nested bounding boxes (keep the larger outer box)
        filtered_boxes = []
        for box in sorted(digit_boxes, key=lambda b: b[2] * b[3], reverse=True): # Sort by area descending
            x, y, w, h = box
            overlap = False
            for fb in filtered_boxes:
                fx, fy, fw, fh = fb
                # Check if current box is largely contained inside existing box
                if (x >= fx - 3 and y >= fy - 3 and 
                    x + w <= fx + fw + 3 and y + h <= fy + fh + 3):
                    overlap = True
                    break
            if not overlap:
                filtered_boxes.append(box)

        # Sort left-to-right primarily, but we will group them into rows later
        return filtered_boxes

    def match_digit(self, digit_img):
        """
        Classifies a segmented digit image by comparing it to standard templates.
        Uses normalized cross-correlation.
        """
        # Resize to standard size (20x30) matching templates
        resized = cv2.resize(digit_img, (20, 30))
        
        best_score = -1
        best_digit = "8" # Fallback guess

        for name, template in self.templates.items():
            # Calculate template match score
            res = cv2.matchTemplate(resized, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            
            if max_val > best_score:
                best_score = max_val
                best_digit = name.split("_")[1]

        # Standard check: If confidence is very low, perform custom 7-segment check
        if best_score < 0.4:
            best_digit = self.classify_7segment(resized)

        return best_digit

    def classify_7segment(self, resized_bin):
        """
        Robust fallback classifier. Splits the 20x30 binary digit into 7 target areas
        and determines which segments are active.
        """
        # 20x30 grid:
        # Segment A: Top horizontal (y: 0-4, x: 3-17)
        # Segment F: Top-left vertical (y: 3-13, x: 0-4)
        # Segment B: Top-right vertical (y: 3-13, x: 16-20)
        # Segment G: Middle horizontal (y: 13-17, x: 3-17)
        # Segment E: Bottom-left vertical (y: 17-27, x: 0-4)
        # Segment C: Bottom-right vertical (y: 17-27, x: 16-20)
        # Segment D: Bottom horizontal (y: 26-30, x: 3-17)
        
        segments = {
            'a': resized_bin[0:5, 3:17],
            'f': resized_bin[3:13, 0:5],
            'b': resized_bin[3:13, 15:20],
            'g': resized_bin[13:17, 3:17],
            'e': resized_bin[17:27, 0:5],
            'c': resized_bin[17:27, 15:20],
            'd': resized_bin[25:30, 3:17]
        }
        
        states = {}
        for seg, area in segments.items():
            # Calculate ratio of white pixels (255)
            ratio = np.mean(area == 255)
            states[seg] = 1 if ratio > 0.3 else 0

        # Match state to digit
        digit_map = {
            (1, 1, 1, 0, 1, 1, 1): "0",
            (0, 0, 1, 0, 0, 1, 0): "1",
            (1, 0, 1, 1, 1, 0, 1): "2",
            (1, 0, 1, 1, 0, 1, 1): "3",
            (0, 1, 1, 1, 0, 1, 0): "4",
            (1, 1, 0, 1, 0, 1, 1): "5",
            (1, 1, 0, 1, 1, 1, 1): "6",
            (1, 0, 1, 0, 0, 1, 0): "7",
            (1, 1, 1, 1, 1, 1, 1): "8",
            (1, 1, 1, 1, 0, 1, 1): "9",
            # Common partial/skewed shapes fallback
            (0, 0, 1, 0, 0, 1, 1): "1", # slanted 1
            (1, 1, 1, 1, 0, 1, 0): "9", # 9 without bottom bar
            (1, 1, 1, 0, 0, 1, 0): "7", # 7 with left bar
            (1, 1, 1, 1, 1, 0, 1): "0", # 0 with middle bar weak
        }
        
        state_tuple = (states['a'], states['f'], states['b'], states['g'], states['e'], states['c'], states['d'])
        return digit_map.get(state_tuple, "8") # Default fallback

    def extract_readings(self, img_path):
        """
        Main OCR entry point. Takes image path, runs pipeline, clusters digits,
        and applies medical heuristics to return:
        (systolic, diastolic, pulse, processed_img_path)
        """
        try:
            # 1. Preprocess
            img_resized, cleaned = self.preprocess_image(img_path)
            
            # Save processed preview image to file to show in Kivy UI
            dir_name = os.path.dirname(img_path)
            proc_filename = "proc_" + os.path.basename(img_path)
            proc_path = os.path.join(dir_name, proc_filename)
            cv2.imwrite(proc_path, cleaned)

            # 2. Segment
            boxes = self.segment_digits(cleaned)
            if not boxes:
                return None, None, None, proc_path

            # 3. Cluster digits vertically into rows (SYS, DIA, PULSE)
            # Sort boxes by y coordinate
            boxes_y_sorted = sorted(boxes, key=lambda b: b[1])
            
            # Group into rows based on y overlap or spacing
            rows = []
            current_row = [boxes_y_sorted[0]]
            row_y_threshold = int(img_resized.shape[0] * 0.08) # 8% of image height

            for box in boxes_y_sorted[1:]:
                # If current box top is significantly lower than the average bottom of current row
                avg_bottom = sum(b[1] + b[3] for b in current_row) / len(current_row)
                if box[1] > avg_bottom + row_y_threshold:
                    # Save current row and start new row
                    rows.append(current_row)
                    current_row = [box]
                else:
                    current_row.append(box)
            rows.append(current_row) # Add final row

            # Now, for each row, sort left-to-right (by x) and extract digit characters
            numbers = []
            for r in rows:
                sorted_row = sorted(r, key=lambda b: b[0])
                num_str = ""
                for box in sorted_row:
                    x, y, w, h = box
                    digit_crop = cleaned[y:y+h, x:x+w]
                    digit = self.match_digit(digit_crop)
                    num_str += digit
                
                try:
                    val = int(num_str)
                    # Filter implausible numbers (e.g. single digits or > 300)
                    if 10 <= val <= 299:
                        numbers.append(val)
                except ValueError:
                    pass

            # 4. Apply Clinical Range Heuristic to assign Sys, Dia, Pulse
            # Systolic is always the highest number (typically 90-190)
            # Diastolic is intermediate (typically 50-110)
            # Pulse is usually lowest or close to Diastolic (typically 40-120)
            # Let's sort the extracted numbers in descending order
            numbers = sorted(list(set(numbers)), reverse=True)

            sys, dia, pulse = None, None, None
            
            if len(numbers) >= 3:
                # Standard case: 3 readings detected
                # Check logic: Sys > Dia
                sys = numbers[0]
                # Distinguish Dia and Pulse. Typically Diastolic is the middle one and Pulse is lowest, 
                # but sometimes Pulse is higher than Diastolic.
                # However, on BP screens, the order is strictly: Top=Sys, Middle=Dia, Bottom=Pulse.
                # If we trust our vertical clustering, we should map them by row index:
                # Row 0 -> Sys, Row 1 -> Dia, Row 2 -> Pulse.
                # Let's map by row index first, and if that fails, use value sorting.
                row_vals = []
                for r in rows:
                    sorted_row = sorted(r, key=lambda b: b[0])
                    row_str = "".join(self.match_digit(cleaned[b[1]:b[1]+b[3], b[0]:b[0]+b[2]]) for b in sorted_row)
                    try:
                        val = int(row_str)
                        if 10 <= val <= 299:
                            row_vals.append(val)
                    except ValueError:
                        pass
                
                if len(row_vals) >= 3:
                    sys, dia, pulse = row_vals[0], row_vals[1], row_vals[2]
                else:
                    # Fallback to sorted values
                    sys, dia, pulse = numbers[0], numbers[1], numbers[2]

            elif len(numbers) == 2:
                # Only 2 readings detected (probably Sys and Dia, or Sys and Pulse)
                # Assign highest to Sys, lower to Dia.
                sys = numbers[0]
                dia = numbers[1]
                pulse = None
            elif len(numbers) == 1:
                # Only 1 reading detected
                sys = numbers[0]
                
            # Perform sanity range checks to make sure we don't output absurd values
            if sys and not (70 <= sys <= 250): sys = None
            if dia and not (40 <= dia <= 150): dia = None
            if pulse and not (35 <= pulse <= 220): pulse = None

            return sys, dia, pulse, proc_path

        except Exception as e:
            print(f"OCR Exception: {e}")
            # Return empty readings and original path
            return None, None, None, img_path

    def get_mock_readings(self):
        """
        Simulates OCR results for testing/desktop environments.
        """
        # Returns typical blood pressure readings randomly for testing
        import random
        sys = random.randint(115, 145)
        dia = random.randint(70, 95)
        pulse = random.randint(60, 90)
        return sys, dia, pulse
