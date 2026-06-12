import os
from kivy.utils import platform

# Global flags
is_android = platform == 'android'

if is_android:
    from jnius import autoclass, cast
    from android.permissions import request_permissions, Permission
    
    # Android System Classes
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    activity = PythonActivity.mActivity
    Intent = autoclass('android.content.Intent')
    Uri = autoclass('android.net.Uri')
    File = autoclass('java.io.File')
    Environment = autoclass('android.os.Environment')
    MediaStore = autoclass('android.provider.MediaStore')
    FileProvider = autoclass('androidx.core.content.FileProvider')
    BitmapFactory = autoclass('android.graphics.BitmapFactory')
    PrintHelper = autoclass('androidx.print.PrintHelper')
else:
    activity = None

class AndroidHelper:
    @staticmethod
    def request_permissions(callback=None):
        """
        Requests Android runtime permissions. Calls callback(granted) when done.
        """
        if not is_android:
            if callback:
                callback(True)
            return

        permissions = [
            Permission.CAMERA,
            Permission.READ_EXTERNAL_STORAGE,
            Permission.WRITE_EXTERNAL_STORAGE
        ]
        
        # For Android 13+ (API 33), read media images is needed
        try:
            # We can check the Android build SDK version dynamically
            BuildVersion = autoclass('android.os.Build$VERSION')
            sdk_int = BuildVersion.SDK_INT
            if sdk_int >= 33:
                # Add READ_MEDIA_IMAGES permission
                # Pyjnius can load it by name
                READ_MEDIA_IMAGES = "android.permission.READ_MEDIA_IMAGES"
                permissions.append(READ_MEDIA_IMAGES)
        except Exception as e:
            print(f"Error checking SDK version: {e}")

        def check_permissions(permissions_list, grant_results):
            # Check if all permissions are granted
            all_granted = all(grant_results)
            if callback:
                callback(all_granted)

        request_permissions(permissions, check_permissions)

    @staticmethod
    def get_public_dir(dir_type="Documents"):
        """
        Returns a path to a public directory for exporting files.
        On Android: returns public Documents or Download folder.
        On Desktop: returns standard local directory.
        """
        if not is_android:
            fallback_dir = os.path.abspath("./exports")
            if not os.path.exists(fallback_dir):
                os.makedirs(fallback_dir)
            return fallback_dir

        try:
            if dir_type == "Downloads":
                enum_type = Environment.DIRECTORY_DOWNLOADS
            else:
                enum_type = Environment.DIRECTORY_DOCUMENTS
                
            public_file = Environment.getExternalStoragePublicDirectory(enum_type)
            path = public_file.getAbsolutePath()
            if not os.path.exists(path):
                os.makedirs(path)
            return path
        except Exception as e:
            print(f"Error getting public dir: {e}")
            # Fallback to internal storage path
            return activity.getExternalFilesDir(None).getAbsolutePath()

    @staticmethod
    def open_camera(output_path, on_complete):
        """
        Launches the native camera.
        output_path: path where the captured image should be saved.
        on_complete: callback function taking (success, file_path).
        """
        if not is_android:
            # Desktop implementation: Opens OpenCV webcam preview to capture frame
            AndroidHelper._open_desktop_camera(output_path, on_complete)
            return

        try:
            # Create the file where the image should go
            photo_file = File(output_path)
            # Use FileProvider for secure URI sharing
            package_name = activity.getPackageName()
            provider_authority = f"{package_name}.fileprovider"
            file_uri = FileProvider.getUriForFile(activity, provider_authority, photo_file)

            # Create Camera Intent
            intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
            intent.putExtra(MediaStore.EXTRA_OUTPUT, file_uri)
            
            # Grant permission to the camera to write to the URI
            intent.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION)

            # Define Kivy activity result listener
            # We bind to activity events to get the camera return callback
            def on_activity_result(request_code, result_code, intent_data):
                # Request code for camera is 1001
                if request_code == 1001:
                    activity.unbind(on_activity_result=on_activity_result)
                    # RESULT_OK is usually -1
                    if result_code == -1: # RESULT_OK
                        on_complete(True, output_path)
                    else:
                        on_complete(False, None)

            activity.bind(on_activity_result=on_activity_result)
            activity.startActivityForResult(intent, 1001)

        except Exception as e:
            print(f"Error launching Android Camera Intent: {e}")
            on_complete(False, None)

    @staticmethod
    def open_gallery(on_complete):
        """
        Launches the native photo gallery to select a picture.
        on_complete: callback function taking (success, selected_file_path).
        """
        if not is_android:
            # Desktop implementation: Opens standard Tkinter file selector
            AndroidHelper._open_desktop_gallery(on_complete)
            return

        try:
            intent = Intent(Intent.ACTION_PICK, MediaStore.Images.Media.EXTERNAL_CONTENT_URI)
            intent.setType("image/*")

            def on_activity_result(request_code, result_code, intent_data):
                # Request code for gallery is 1002
                if request_code == 1002:
                    activity.unbind(on_activity_result=on_activity_result)
                    if result_code == -1 and intent_data is not None:
                        # Extract selected image URI
                        selected_image_uri = intent_data.getData()
                        # Query the cursor to find the real file path
                        real_path = AndroidHelper._get_real_path_from_uri(selected_image_uri)
                        if real_path and os.path.exists(real_path):
                            on_complete(True, real_path)
                        else:
                            # Copy Uri stream to app temporary files if file path can't be resolved directly
                            temp_path = AndroidHelper._copy_uri_stream_to_temp(selected_image_uri)
                            if temp_path:
                                on_complete(True, temp_path)
                            else:
                                on_complete(False, None)
                    else:
                        on_complete(False, None)

            activity.bind(on_activity_result=on_activity_result)
            activity.startActivityForResult(intent, 1002)

        except Exception as e:
            print(f"Error launching Android Gallery Intent: {e}")
            on_complete(False, None)

    @staticmethod
    def print_pdf(pdf_path, title="Blood Pressure Report"):
        """
        Prints a PDF report using Android's Print Framework.
        Falls back to sharing / system view on failure.
        """
        if not is_android:
            print(f"[Desktop Mock] Printing PDF: {pdf_path}")
            # Try to open PDF in default viewer
            try:
                os.startfile(pdf_path)
            except AttributeError:
                import subprocess
                subprocess.call(['open', pdf_path])
            return

        try:
            # Direct Android PrintManager approach
            # Requires implementing PrintDocumentAdapter.
            # To avoid complex Java class bindings in Python, we launch the ACTION_VIEW intent 
            # with the PDF, allowing the user to print directly from the system PDF viewer app.
            # This is 100% stable and does not cause Pyjnius thread locks.
            file_to_print = File(pdf_path)
            package_name = activity.getPackageName()
            uri = FileProvider.getUriForFile(activity, f"{package_name}.fileprovider", file_to_print)

            intent = Intent(Intent.ACTION_VIEW)
            intent.setDataAndType(uri, "application/pdf")
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            intent.addFlags(Intent.FLAG_ACTIVITY_NO_HISTORY)
            
            # Start chooser so user can open in print services or PDF reader
            chooser = Intent.createChooser(intent, "Open Report to Print/Share")
            activity.startActivity(chooser)
        except Exception as e:
            print(f"Error printing PDF: {e}")
            # Try basic share fallback
            AndroidHelper.share_pdf(pdf_path)

    @staticmethod
    def print_image(image_path, job_name="Blood Pressure Graph"):
        """
        Uses AndroidX PrintHelper to print an image/chart directly to a Wi-Fi printer.
        """
        if not is_android:
            print(f"[Desktop Mock] Printing Image: {image_path}")
            try:
                os.startfile(image_path)
            except Exception:
                pass
            return

        try:
            bitmap = BitmapFactory.decodeFile(image_path)
            if bitmap is None:
                raise ValueError("Could not decode image file to bitmap")
                
            print_helper = PrintHelper(activity)
            print_helper.setScaleMode(PrintHelper.SCALE_MODE_FIT)
            print_helper.printBitmap(job_name, bitmap)
        except Exception as e:
            print(f"Error printing image via PrintHelper: {e}")

    @staticmethod
    def share_pdf(pdf_path):
        """
        Shares a PDF file via standard Android share sheet.
        """
        if not is_android:
            print(f"[Desktop Mock] Sharing PDF: {pdf_path}")
            return

        try:
            pdf_file = File(pdf_path)
            package_name = activity.getPackageName()
            uri = FileProvider.getUriForFile(activity, f"{package_name}.fileprovider", pdf_file)

            intent = Intent(Intent.ACTION_SEND)
            intent.setType("application/pdf")
            intent.putExtra(Intent.EXTRA_STREAM, uri)
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)

            chooser = Intent.createChooser(intent, "Share Report PDF")
            activity.startActivity(chooser)
        except Exception as e:
            print(f"Error sharing PDF: {e}")

    # Desktop Implementations (Private)
    @staticmethod
    def _open_desktop_camera(output_path, on_complete):
        """
        Fallback camera for PC. Opens webcam, shows a preview window.
        Press 'SPACE' to snap, 'ESC' to cancel.
        """
        import cv2
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Webcam not available.")
            on_complete(False, None)
            return

        print("Press SPACE to take photo, ESC to cancel.")
        captured = False
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Add guide line on screen
            h, w = frame.shape[:2]
            cv2.rectangle(frame, (int(w*0.25), int(h*0.2)), (int(w*0.75), int(h*0.8)), (0, 255, 0), 2)
            cv2.putText(frame, "Align Monitor Screen & Press SPACE", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            cv2.imshow("Desktop Camera Preview (Press SPACE to Capture)", frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == 32: # SPACE
                # Recapture clean frame without lines
                ret, clean_frame = cap.read()
                if ret:
                    # Ensure parent folder exists
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    cv2.imwrite(output_path, clean_frame)
                    captured = True
                break
            elif key == 27: # ESC
                break

        cap.release()
        cv2.destroyAllWindows()
        
        if captured:
            on_complete(True, output_path)
        else:
            on_complete(False, None)

    @staticmethod
    def _open_desktop_gallery(on_complete):
        """
        Fallback gallery for PC. Opens a Tkinter file chooser.
        """
        try:
            import tkinter as tk
            from tkinter import filedialog
            
            root = tk.Tk()
            root.withdraw() # Hide root window
            
            file_path = filedialog.askopenfilename(
                title="Select Blood Pressure Monitor Photo",
                filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp")]
            )
            
            # Close tkinter context
            root.destroy()
            
            if file_path:
                on_complete(True, file_path)
            else:
                on_complete(False, None)
        except Exception as e:
            print(f"Desktop Tkinter dialogue error: {e}")
            # Try Kivy filechooser fallback if tkinter is not installed
            on_complete(False, None)

    # Android Uri Utilities (Private)
    @staticmethod
    def _get_real_path_from_uri(content_uri):
        """
        Queries Android content resolver to find the absolute file path of a gallery image.
        """
        try:
            cursor = activity.getContentResolver().query(content_uri, None, None, None, None)
            if cursor is not None:
                cursor.moveToFirst()
                idx = cursor.getColumnIndex(MediaStore.Images.ImageColumns.DATA)
                if idx != -1:
                    path = cursor.getString(idx)
                    cursor.close()
                    return path
                cursor.close()
        except Exception as e:
            print(f"Error resolving Uri path: {e}")
        return None

    @staticmethod
    def _copy_uri_stream_to_temp(content_uri):
        """
        Helper to copy a file stream from an Android Content Provider Uri to a local app temporary file.
        This is necessary for gallery pictures stored in cloud services or sandboxed folders.
        """
        try:
            input_stream = activity.getContentResolver().openInputStream(content_uri)
            # Get internal cache dir
            cache_dir = activity.getCacheDir().getAbsolutePath()
            temp_file = File(cache_dir, "temp_gallery_upload.jpg")
            
            FileOutputStream = autoclass('java.io.FileOutputStream')
            output_stream = FileOutputStream(temp_file)
            
            # Buffer copy
            # Use byte array in Java via jnius
            j_byte = autoclass('java.lang.Byte')
            # Create a 4KB buffer
            buffer = bytearray(4096)
            
            # Since Pyjnius can call read on InputStream directly, we can read chunks
            # In python, we read the stream and write bytes
            # For simplicity, we can read all bytes if not too large, or write a loop
            # A simple loop using python wrapper is fast enough for single images
            chunk = input_stream.read()
            while chunk != -1:
                output_stream.write(chunk)
                chunk = input_stream.read()
                
            input_stream.close()
            output_stream.close()
            return temp_file.getAbsolutePath()
        except Exception as e:
            print(f"Error copying Uri stream: {e}")
        return None
