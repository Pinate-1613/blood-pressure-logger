import os
from kivy.config import Config
# Prevent Kivy from parsing system arguments if compiled/run from terminal
Config.set('kivy', 'log_level', 'info')

from kivy.core.window import Window
from kivy.utils import platform
from kivy.uix.screenmanager import ScreenManager, Screen

# KivyMD core imports
from kivymd.app import MDApp
from kivymd.uix.bottomnavigation import MDBottomNavigation, MDBottomNavigationItem
from kivymd.uix.snackbar import Snackbar

# Local Imports
from database import BPDatabase
from android_helper import AndroidHelper
from ui_screens import DashboardScreen, HistoryScreen, ReportScreen, SettingsScreen, CaptureScreen

# Desktop window layout simulation
if platform != 'android':
    Window.size = (400, 720)


class BPLoggerApp(MDApp):
    def __init__(self, **kwargs):
        super(BPLoggerApp, self).__init__(**kwargs)
        self.db = None
        self.high_contrast = False
        self.snackbar = None

    def build(self):
        # 1. Initialize SQLite Database
        self.db = BPDatabase()
        
        # 2. Configure Theme Styles from settings
        saved_theme = self.db.get_setting("theme_style", "Light")
        saved_contrast = self.db.get_setting("high_contrast", "0")
        
        self.theme_cls.primary_palette = "Teal"
        self.theme_cls.accent_palette = "Amber"
        self.theme_cls.theme_style = saved_theme
        self.high_contrast = saved_contrast == "1"

        # 3. Setup Screen Manager
        self.sm = ScreenManager()

        # Main Screen (contains bottom navigation tabs)
        main_screen = Screen(name='main')
        
        # Bottom Navigation
        bottom_nav = MDBottomNavigation()

        # Tab 1: Dashboard
        tab1 = MDBottomNavigationItem(
            name='dashboard_tab',
            text='Dashboard',
            icon='heart-pulse',
            on_tab_press=self.on_tab_switch
        )
        self.dashboard = DashboardScreen(self)
        tab1.add_widget(self.dashboard)
        bottom_nav.add_widget(tab1)

        # Tab 2: History
        tab2 = MDBottomNavigationItem(
            name='history_tab',
            text='History',
            icon='history',
            on_tab_press=self.on_tab_switch
        )
        self.history = HistoryScreen(self)
        tab2.add_widget(self.history)
        bottom_nav.add_widget(tab2)

        # Tab 3: Reports
        tab3 = MDBottomNavigationItem(
            name='reports_tab',
            text='Reports',
            icon='file-pdf-box',
            on_tab_press=self.on_tab_switch
        )
        self.report = ReportScreen(self)
        tab3.add_widget(self.report)
        bottom_nav.add_widget(tab3)

        # Tab 4: Settings
        tab4 = MDBottomNavigationItem(
            name='settings_tab',
            text='Settings',
            icon='cog',
            on_tab_press=self.on_tab_switch
        )
        self.settings = SettingsScreen(self)
        tab4.add_widget(self.settings)
        bottom_nav.add_widget(tab4)

        main_screen.add_widget(bottom_nav)
        self.sm.add_widget(main_screen)

        # Capture / OCR Review Screen (separate screen outside bottom navigation tabs)
        self.capture_screen = CaptureScreen(self, name='capture')
        self.sm.add_widget(self.capture_screen)

        return self.sm

    def on_tab_switch(self, tab_instance):
        """
        Refresh active tab views dynamically upon tab switching
        """
        if tab_instance.name == 'dashboard_tab':
            self.dashboard.update_dashboard()
        elif tab_instance.name == 'history_tab':
            self.history.update_content()
        elif tab_instance.name == 'reports_tab':
            self.report.build_ui()
        elif tab_instance.name == 'settings_tab':
            self.settings.build_ui()

    def show_snackbar(self, text):
        if self.snackbar:
            self.snackbar.dismiss()
        self.snackbar = Snackbar(text=text, duration=3.0)
        self.snackbar.open()

    # CAMERA & GALLERY BRIDGES
    def trigger_camera_capture(self, *args):
        # 1. Check permissions first
        AndroidHelper.request_permissions(callback=self._permission_callback_camera)

    def _permission_callback_camera(self, granted):
        if not granted:
            self.show_snackbar("Error: Camera permissions are required to take photos.")
            return

        # Prepare output path in user data folder
        filename = "capture_" + self.db.get_setting("user_name", "User") + ".jpg"
        # Store in app user data directory
        temp_dir = self.user_data_dir if self.user_data_dir else "."
        output_path = os.path.abspath(os.path.join(temp_dir, filename))

        # Launch Camera Intent
        AndroidHelper.open_camera(output_path, self._on_camera_capture_complete)

    def _on_camera_capture_complete(self, success, file_path):
        if success and file_path and os.path.exists(file_path):
            self.show_snackbar("Photo captured. Running OCR display analysis...")
            # Route to Capture Review screen
            self.root.current = 'capture'
            self.capture_screen.load_image_and_run_ocr(file_path)
        else:
            self.show_snackbar("Camera capture cancelled or failed.")

    def trigger_gallery_picker(self, *args):
        # Check permissions
        AndroidHelper.request_permissions(callback=self._permission_callback_gallery)

    def _permission_callback_gallery(self, granted):
        if not granted:
            self.show_snackbar("Error: Storage permissions are required to load photos.")
            return

        # Launch picker
        AndroidHelper.open_gallery(self._on_gallery_pick_complete)

    def _on_gallery_pick_complete(self, success, file_path):
        if success and file_path and os.path.exists(file_path):
            self.show_snackbar("Photo selected. Running OCR display analysis...")
            self.root.current = 'capture'
            self.capture_screen.load_image_and_run_ocr(file_path)
        else:
            self.show_snackbar("No image selected from gallery.")

    # MANUAL LOG BRIDGES
    def trigger_manual_log(self, *args):
        self.root.current = 'capture'
        self.capture_screen.load_manual_log()


if __name__ == '__main__':
    BPLoggerApp().run()
