from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.graphics import Color, Line, Rectangle, Ellipse, InstructionGroup
from kivy.properties import ListProperty, ObjectProperty, NumericProperty
from kivy.metrics import dp

class BPLineChart(Widget):
    """
    A custom canvas-drawn line chart for blood pressure readings.
    Plots Systolic (upper line) and Diastolic (lower line) values.
    """
    records = ListProperty([])

    def __init__(self, **kwargs):
        super(BPLineChart, self).__init__(**kwargs)
        self.bind(pos=self.draw_chart, size=self.draw_chart, records=self.draw_chart)
        # Store label widgets so we can update/remove them
        self.labels = []

    def clear_labels(self):
        for label in self.labels:
            self.remove_widget(label)
        self.labels = []

    def draw_chart(self, *args):
        self.canvas.clear()
        self.clear_labels()

        if not self.records:
            # Draw a simple placeholder text
            no_data_label = Label(
                text="No data available for this period",
                pos=self.pos,
                size=self.size,
                font_size='16sp',
                color=(0.5, 0.5, 0.5, 1)
            )
            self.add_widget(no_data_label)
            self.labels.append(no_data_label)
            return

        # Setup parameters
        padding_left = dp(45)
        padding_right = dp(20)
        padding_top = dp(25)
        padding_bottom = dp(35)

        width = self.width - padding_left - padding_right
        height = self.height - padding_top - padding_bottom

        if width <= 0 or height <= 0:
            return

        # Prepare and reverse data to chronological order (records usually come desc)
        sorted_records = sorted(self.records, key=lambda x: x['timestamp'])
        n_points = len(sorted_records)

        # Get min and max values to scale Y-axis
        all_sys = [r['systolic'] for r in sorted_records]
        all_dia = [r['diastolic'] for r in sorted_records]
        
        max_val = max(max(all_sys), 150)  # At least show up to 150 mmHg
        min_val = min(min(all_dia), 60)   # At least show down to 60 mmHg
        
        # Round min/max values to nice multiples of 20
        max_val = ((max_val // 20) + 1) * 20
        min_val = max(0, ((min_val // 20) - 1) * 20)
        
        val_range = max_val - min_val
        if val_range == 0:
            val_range = 100

        # Draw Grid and Y-Axis Labels
        with self.canvas:
            # Grid background
            Color(0.95, 0.95, 0.96, 1)
            Rectangle(pos=(self.x + padding_left, self.y + padding_bottom), size=(width, height))
            
            # Grid lines (every 20 mmHg)
            y_step = 20
            curr_y = min_val
            while curr_y <= max_val:
                y_ratio = (curr_y - min_val) / val_range
                canvas_y = self.y + padding_bottom + (y_ratio * height)
                
                # Grid line
                Color(0.85, 0.85, 0.88, 1)
                Line(points=[self.x + padding_left, canvas_y, self.x + padding_left + width, canvas_y], width=dp(1))
                
                # Y label
                y_label = Label(
                    text=str(int(curr_y)),
                    font_size='11sp',
                    color=(0.3, 0.3, 0.3, 1),
                    size_hint=(None, None),
                    size=(padding_left - dp(5), dp(20)),
                    pos=(self.x, canvas_y - dp(10)),
                    halign='right',
                    valign='middle'
                )
                y_label.bind(texture_size=y_label.setter('size'))
                self.add_widget(y_label)
                self.labels.append(y_label)
                
                curr_y += y_step

        # Calculate coordinates for lines
        sys_points = []
        dia_points = []
        x_coords = []

        for i, r in enumerate(sorted_records):
            # X positioning
            if n_points > 1:
                x_ratio = i / (n_points - 1)
            else:
                x_ratio = 0.5
            canvas_x = self.x + padding_left + (x_ratio * width)
            x_coords.append(canvas_x)

            # Y positioning (Systolic)
            sys_val = r['systolic']
            sys_ratio = (sys_val - min_val) / val_range
            sys_y = self.y + padding_bottom + (sys_ratio * height)
            sys_points.extend([canvas_x, sys_y])

            # Y positioning (Diastolic)
            dia_val = r['diastolic']
            dia_ratio = (dia_val - min_val) / val_range
            dia_y = self.y + padding_bottom + (dia_ratio * height)
            dia_points.extend([canvas_x, dia_y])

            # Draw date/time labels on X axis for key points (max 5 labels to avoid crowding)
            if n_points <= 5 or i % (n_points // 4 or 1) == 0 or i == n_points - 1:
                # Format: MM-DD or HH:MM
                try:
                    dt = datetime.strptime(r['timestamp'], "%Y-%m-%d %H:%M:%S")
                    lbl_text = dt.strftime("%m-%d\n%H:%M")
                except ValueError:
                    lbl_text = r['timestamp'][:10]
                    
                x_label = Label(
                    text=lbl_text,
                    font_size='9sp',
                    color=(0.3, 0.3, 0.3, 1),
                    size_hint=(None, None),
                    size=(dp(50), padding_bottom - dp(5)),
                    pos=(canvas_x - dp(25), self.y),
                    halign='center',
                    valign='top'
                )
                self.add_widget(x_label)
                self.labels.append(x_label)

        # Draw trend lines & dots on Canvas
        with self.canvas:
            # 1. Draw Systolic Line (Coral Red: #EF4444)
            if len(sys_points) >= 4:
                Color(0.93, 0.27, 0.27, 1)  # Red
                Line(points=sys_points, width=dp(2.5))
            
            # 2. Draw Diastolic Line (Teal Blue: #06B6D4)
            if len(dia_points) >= 4:
                Color(0.02, 0.71, 0.83, 1)  # Teal
                Line(points=dia_points, width=dp(2.5))

            # 3. Draw Dots on top
            dot_r = dp(4)
            for i, r in enumerate(sorted_records):
                cx = x_coords[i]
                
                # Systolic dot
                Color(0.93, 0.27, 0.27, 1)
                Ellipse(pos=(cx - dot_r, sys_points[2 * i + 1] - dot_r), size=(2 * dot_r, 2 * dot_r))
                Color(1, 1, 1, 1)
                Ellipse(pos=(cx - dot_r/2, sys_points[2 * i + 1] - dot_r/2), size=(dot_r, dot_r))
                
                # Diastolic dot
                Color(0.02, 0.71, 0.83, 1)
                Ellipse(pos=(cx - dot_r, dia_points[2 * i + 1] - dot_r), size=(2 * dot_r, 2 * dot_r))
                Color(1, 1, 1, 1)
                Ellipse(pos=(cx - dot_r/2, dia_points[2 * i + 1] - dot_r/2), size=(dot_r, dot_r))


class BPRangeBar(Widget):
    """
    A custom horizontal gauge widget displaying standard AHA/ESC 
    blood pressure color categories (Normal, Elevated, Stage 1, Stage 2, Crisis)
    and an indicator dot showing where the user's reading falls.
    """
    systolic = NumericProperty(120)
    diastolic = NumericProperty(80)

    def __init__(self, **kwargs):
        super(BPRangeBar, self).__init__(**kwargs)
        self.bind(pos=self.draw_widget, size=self.draw_widget, systolic=self.draw_widget, diastolic=self.draw_widget)

    def get_bp_category(self, sys, dia):
        # AHA/ESC categories
        if sys < 120 and dia < 80:
            return "Normal", (0.02, 0.65, 0.40, 1)     # Green: #059669
        elif 120 <= sys < 130 and dia < 80:
            return "Elevated", (0.85, 0.60, 0.05, 1)   # Yellow/Gold: #D97706
        elif (130 <= sys < 140) or (80 <= dia < 90):
            return "High (Stage 1)", (0.90, 0.35, 0.05, 1) # Orange: #EA580C
        elif (140 <= sys < 180) or (90 <= dia < 120):
            return "High (Stage 2)", (0.85, 0.15, 0.15, 1) # Red: #DC2626
        else:
            return "Hypertensive Crisis", (0.6, 0.05, 0.1, 1) # Crimson/Purple-Red

    def draw_widget(self, *args):
        self.canvas.clear()
        
        bar_height = dp(14)
        margin_x = dp(15)
        margin_y = dp(25)
        
        # Available drawing width
        draw_w = self.width - 2 * margin_x
        if draw_w <= 0:
            return

        # Segments colors and weights
        # Normal, Elevated, Stage 1, Stage 2, Crisis
        seg_colors = [
            (0.02, 0.65, 0.40, 1), # Green
            (0.85, 0.60, 0.05, 1), # Yellow
            (0.90, 0.35, 0.05, 1), # Orange
            (0.85, 0.15, 0.15, 1), # Red
            (0.6, 0.05, 0.1, 1),   # Crimson
        ]
        
        # Draw background color bands
        num_segments = len(seg_colors)
        seg_w = draw_w / num_segments
        
        with self.canvas:
            for i, col in enumerate(seg_colors):
                Color(*col)
                seg_x = self.x + margin_x + i * seg_w
                Rectangle(pos=(seg_x, self.y + margin_y), size=(seg_w, bar_height))
                
            # Draw dividers
            Color(1, 1, 1, 0.7)
            for i in range(1, num_segments):
                divider_x = self.x + margin_x + i * seg_w
                Line(points=[divider_x, self.y + margin_y, divider_x, self.y + margin_y + bar_height], width=dp(1.5))

            # Determine position of the user's reading along the bar
            # We map Systolic (range 80 to 200) to progress bar width
            sys = self.systolic
            sys_min, sys_max = 80, 200
            
            # Map diastolic (range 40 to 120) to check severity
            dia = self.diastolic
            
            # Choose the worst-performing metric to position the dot
            category, cat_color = self.get_bp_category(sys, dia)
            
            # Position mapping based on category for indicator dot
            if category == "Normal":
                cat_idx = 0
                cat_progress = (sys - 80) / (120 - 80) if sys >= 80 else 0
            elif category == "Elevated":
                cat_idx = 1
                cat_progress = (sys - 120) / (130 - 120)
            elif category == "High (Stage 1)":
                cat_idx = 2
                # Could be triggered by either
                sys_p = (sys - 130) / (140 - 130)
                dia_p = (dia - 80) / (90 - 80)
                cat_progress = max(sys_p, dia_p)
            elif category == "High (Stage 2)":
                cat_idx = 3
                sys_p = (sys - 140) / (180 - 140)
                dia_p = (dia - 90) / (120 - 90)
                cat_progress = max(sys_p, dia_p)
            else: # Hypertensive Crisis
                cat_idx = 4
                sys_p = (sys - 180) / (220 - 180) if sys <= 220 else 1.0
                dia_p = (dia - 120) / (140 - 120) if dia <= 140 else 1.0
                cat_progress = max(sys_p, dia_p)

            # Clamp progress within [0, 1]
            cat_progress = min(max(cat_progress, 0.0), 1.0)
            
            # Indicator x position
            indicator_x = self.x + margin_x + (cat_idx * seg_w) + (cat_progress * seg_w)
            
            # Draw pointer dot
            Color(0.2, 0.2, 0.2, 1) # Dark outer ring
            indicator_y = self.y + margin_y + bar_height / 2
            dot_radius = dp(7)
            Ellipse(pos=(indicator_x - dot_radius, indicator_y - dot_radius), size=(2 * dot_radius, 2 * dot_radius))
            
            # Draw inner color dot matching the category
            Color(*cat_color)
            inner_radius = dp(5)
            Ellipse(pos=(indicator_x - inner_radius, indicator_y - inner_radius), size=(2 * inner_radius, 2 * inner_radius))
            
            # Draw white center
            Color(1, 1, 1, 1)
            core_radius = dp(2)
            Ellipse(pos=(indicator_x - core_radius, indicator_y - core_radius), size=(2 * core_radius, 2 * core_radius))
            
            # Draw text showing Category and Value below
            # Since drawing labels on canvas is easier, let's create layout text manually
            # But inside KivyMD we'll also show this text in structured MDLabels.
            # We draw a small triangular indicator pointing to the dot.
            Color(0.2, 0.2, 0.2, 1)
            Line(points=[
                indicator_x, indicator_y + dot_radius,
                indicator_x - dp(4), indicator_y + dot_radius + dp(6),
                indicator_x + dp(4), indicator_y + dot_radius + dp(6),
                indicator_x, indicator_y + dot_radius
            ], close=True)
            
            # Draw outline for the entire bar
            Color(0.7, 0.7, 0.7, 0.5)
            Line(rect=(self.x + margin_x, self.y + margin_y, draw_w, bar_height), width=dp(1))
            
            # Category Label
            cat_label = Label(
                text=f"{category} ({sys}/{dia} mmHg)",
                font_size='13sp',
                bold=True,
                color=(0.15, 0.15, 0.15, 1),
                size_hint=(None, None),
                size=(draw_w, dp(20)),
                pos=(self.x + margin_x, self.y),
                halign='center',
                valign='middle'
            )
            self.add_widget(cat_label)
