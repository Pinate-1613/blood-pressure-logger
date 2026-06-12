import os
from datetime import datetime, timedelta
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.image import Image
from kivy.uix.widget import Widget as Spacer
from kivy.properties import ObjectProperty, StringProperty, NumericProperty
from kivy.metrics import dp
from kivy.utils import get_color_from_hex

# KivyMD Layout imports
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.floatlayout import MDFloatLayout
from kivymd.uix.card import MDCard
from kivymd.uix.button import MDRaisedButton, MDIconButton, MDFillRoundFlatButton, MDFlatButton
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField
from kivymd.uix.list import MDList, ThreeLineAvatarIconListItem, IconLeftWidget, IconRightWidget
from kivymd.uix.dialog import MDDialog
from kivymd.uix.pickers import MDDatePicker

# Local Imports
from database import BPDatabase
from ocr_engine import BPOcrEngine
from chart_widgets import BPLineChart, BPRangeBar
from pdf_generator import BPPdfGenerator
from android_helper import AndroidHelper

class DashboardScreen(MDBoxLayout):
    """
    Dashboard Panel showing the latest blood pressure reading, 
    classification status, custom range indicator, and camera/gallery triggers.
    """
    def __init__(self, app_ref, **kwargs):
        super(DashboardScreen, self).__init__(**kwargs)
        self.app = app_ref
        self.orientation = 'vertical'
        self.spacing = dp(10)
        self.padding = dp(15)
        self.build_ui()

    def build_ui(self):
        self.clear_widgets()

        # 1. Header welcome banner
        header = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50))
        user_name = self.app.db.get_setting("user_name", "User")
        
        self.welcome_label = MDLabel(
            text=f"Welcome back, [b]{user_name}[/b]",
            font_style="H5" if not self.app.high_contrast else "H4",
            markup=True,
            theme_text_color="Primary"
        )
        header.add_widget(self.welcome_label)
        
        # Sync indicator icon
        header.add_widget(MDIconButton(icon="heart-pulse", theme_text_color="Custom", icon_color=get_color_from_hex("#EF4444")))
        self.add_widget(header)

        # 2. Main reading display card
        self.latest_card = MDCard(
            orientation='vertical',
            padding=dp(15),
            spacing=dp(10),
            size_hint_y=None,
            height=dp(280),
            elevation=4,
            radius=[dp(12), dp(12), dp(12), dp(12)]
        )
        
        card_title = MDLabel(
            text="LATEST READING",
            font_style="Overline",
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(15)
        )
        self.latest_card.add_widget(card_title)

        # Large value layouts
        val_box = MDBoxLayout(orientation='horizontal', spacing=dp(10), size_hint_y=None, height=dp(80))
        
        # Systolic / Diastolic values
        self.bp_value = MDLabel(
            text="-- / --",
            font_style="H2" if not self.app.high_contrast else "H1",
            bold=True,
            size_hint_x=0.65,
            valign='middle'
        )
        val_box.add_widget(self.bp_value)

        # Pulse info box
        pulse_box = MDBoxLayout(orientation='vertical', size_hint_x=0.35)
        self.pulse_icon = MDIconButton(icon="heart", theme_text_color="Custom", icon_color=get_color_from_hex("#EF4444"), size_hint_y=0.4)
        self.pulse_value = MDLabel(
            text="-- bpm",
            font_style="H6" if not self.app.high_contrast else "H5",
            bold=True,
            size_hint_y=0.6
        )
        pulse_box.add_widget(self.pulse_icon)
        pulse_box.add_widget(self.pulse_value)
        
        val_box.add_widget(pulse_box)
        self.latest_card.add_widget(val_box)

        # Status & Date info
        self.status_label = MDLabel(
            text="Status: No Readings Logged Yet",
            font_style="Subtitle1",
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(25)
        )
        self.latest_card.add_widget(self.status_label)

        # Custom canvas range bar gauge
        self.range_bar = BPRangeBar(size_hint_y=None, height=dp(70))
        self.latest_card.add_widget(self.range_bar)
        
        self.add_widget(self.latest_card)

        # 3. Action Buttons Grid
        actions_grid = MDGridLayout(cols=2, spacing=dp(12), size_hint_y=None, height=dp(140))

        # Camera Capture Button
        cam_card = MDCard(
            orientation='vertical',
            padding=dp(10),
            spacing=dp(5),
            elevation=2,
            radius=[dp(12)],
            ripple_behavior=True,
            on_release=self.app.trigger_camera_capture
        )
        cam_card.add_widget(MDIconButton(icon="camera", pos_hint={"center_x": 0.5}, size_hint_y=0.6, icon_size="36sp"))
        cam_card.add_widget(MDLabel(text="CAPTURE DISPLAY", font_style="Button", halign="center", size_hint_y=0.4))
        actions_grid.add_widget(cam_card)

        # Gallery Picker Button
        gallery_card = MDCard(
            orientation='vertical',
            padding=dp(10),
            spacing=dp(5),
            elevation=2,
            radius=[dp(12)],
            ripple_behavior=True,
            on_release=self.app.trigger_gallery_picker
        )
        gallery_card.add_widget(MDIconButton(icon="image", pos_hint={"center_x": 0.5}, size_hint_y=0.6, icon_size="36sp"))
        gallery_card.add_widget(MDLabel(text="SELECT FROM GALLERY", font_style="Button", halign="center", size_hint_y=0.4))
        actions_grid.add_widget(gallery_card)

        self.add_widget(actions_grid)

        # Manual Log Shortcut Button
        self.manual_btn = MDFillRoundFlatButton(
            text="LOG MANUALLY",
            icon="pencil",
            pos_hint={"center_x": 0.5},
            size_hint_x=0.8,
            height=dp(48),
            on_release=self.app.trigger_manual_log
        )
        self.add_widget(self.manual_btn)
        
        # Spacer
        self.add_widget(Spacer(size_hint_y=1))

        self.update_dashboard()

    def update_dashboard(self):
        records = self.app.db.get_all_records(order="DESC")
        
        # Update user name if changed
        user_name = self.app.db.get_setting("user_name", "User")
        self.welcome_label.text = f"Welcome back, [b]{user_name}[/b]"
        
        if records:
            latest = records[0]
            sys = latest['systolic']
            dia = latest['diastolic']
            pulse = latest['pulse']
            ts_str = latest['timestamp']
            
            # Format display
            self.bp_value.text = f"{sys} / {dia}"
            self.pulse_value.text = f"{pulse} bpm" if pulse else "-- bpm"
            
            # Status and color details
            category, color = self.range_bar.get_bp_category(sys, dia)
            color_hex = color.hexval() if hasattr(color, 'hexval') else "#059669"
            
            # Formatted time display
            try:
                dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                time_lbl = dt.strftime("%b %d, %I:%M %p")
            except ValueError:
                time_lbl = ts_str
                
            self.status_label.text = f"Status: [b][color={color_hex}]{category}[/color][/b] ({time_lbl})"
            self.status_label.markup = True
            
            # Update canvas gauge
            self.range_bar.systolic = sys
            self.range_bar.diastolic = dia
            self.range_bar.opacity = 1
        else:
            self.bp_value.text = "-- / --"
            self.pulse_value.text = "-- bpm"
            self.status_label.text = "Status: No Readings Logged Yet"
            self.range_bar.opacity = 0 # Hide range gauge if empty


class CaptureScreen(Screen):
    """
    Review Screen that runs OCR on photo selection, shows preprocessed image 
    for transparent visual validation, and presents fields for manual confirmation/edit.
    """
    def __init__(self, app_ref, **kwargs):
        super(CaptureScreen, self).__init__(**kwargs)
        self.app = app_ref
        self.ocr = BPOcrEngine()
        self.image_path = None
        self.record_id = None # Used if editing existing record
        self.build_ui()

    def build_ui(self):
        main_layout = MDBoxLayout(orientation='vertical')
        
        # 1. Top bar
        self.top_bar = MDLabel(
            text="Confirm Extraction Results",
            font_style="H6" if not self.app.high_contrast else "H5",
            theme_text_color="Primary",
            size_hint_y=None,
            height=dp(50),
            halign="center"
        )
        main_layout.add_widget(self.top_bar)

        # 2. Body ScrollView
        scroll = ScrollView()
        body = MDBoxLayout(orientation='vertical', spacing=dp(15), padding=dp(15), size_hint_y=None)
        body.bind(minimum_height=body.setter('height'))

        # Visual Image Previews Card
        self.img_card = MDCard(
            orientation='vertical',
            padding=dp(5),
            elevation=2,
            size_hint_y=None,
            height=dp(240),
            radius=[dp(8)]
        )
        
        # Dynamic label explaining image state
        self.img_title = MDLabel(text="OCR Preprocessed Scan Grid (Threshold View)", font_style="Caption", halign="center", size_hint_y=None, height=dp(20))
        self.img_card.add_widget(self.img_title)
        
        self.preview_image = Image(allow_stretch=True, keep_ratio=True)
        self.img_card.add_widget(self.preview_image)
        body.add_widget(self.img_card)

        # Input fields
        fields_card = MDCard(
            orientation='vertical',
            padding=dp(15),
            spacing=dp(12),
            elevation=3,
            size_hint_y=None,
            height=dp(360),
            radius=[dp(12)]
        )

        # Systolic Input
        self.sys_input = MDTextField(
            hint_text="Systolic Pressure (SYS mmHg)",
            helper_text="Typical normal range is under 120",
            helper_text_mode="on_focus",
            input_filter="int",
            max_text_length=3
        )
        fields_card.add_widget(self.sys_input)

        # Diastolic Input
        self.dia_input = MDTextField(
            hint_text="Diastolic Pressure (DIA mmHg)",
            helper_text="Typical normal range is under 80",
            helper_text_mode="on_focus",
            input_filter="int",
            max_text_length=3
        )
        fields_card.add_widget(self.dia_input)

        # Pulse Input
        self.pulse_input = MDTextField(
            hint_text="Pulse Rate (PULSE /min)",
            helper_text="Typical resting pulse is 60 - 100",
            helper_text_mode="on_focus",
            input_filter="int",
            max_text_length=3
        )
        fields_card.add_widget(self.pulse_input)

        # Notes Input
        self.note_input = MDTextField(
            hint_text="Notes (optional)",
            helper_text="E.g., took medicine, after walk",
            helper_text_mode="on_focus"
        )
        fields_card.add_widget(self.note_input)
        body.add_widget(fields_card)

        # Save & Cancel Buttons
        btn_layout = MDBoxLayout(orientation='horizontal', spacing=dp(15), size_hint_y=None, height=dp(50))
        
        self.cancel_btn = MDFlatButton(
            text="CANCEL",
            on_release=self.go_back
        )
        btn_layout.add_widget(self.cancel_btn)

        self.save_btn = MDRaisedButton(
            text="CONFIRM & SAVE",
            on_release=self.save_record
        )
        btn_layout.add_widget(self.save_btn)
        
        body.add_widget(btn_layout)
        scroll.add_widget(body)
        main_layout.add_widget(scroll)
        self.add_widget(main_layout)

    def load_image_and_run_ocr(self, img_path):
        self.image_path = img_path
        self.record_id = None
        self.sys_input.text = ""
        self.dia_input.text = ""
        self.pulse_input.text = ""
        self.note_input.text = ""
        self.img_title.text = "Preprocessed display (transparent binary threshold)"

        # Process OCR asynchronously / sequentially
        sys, dia, pulse, proc_path = self.ocr.extract_readings(img_path)
        
        # Display preprocessed binary image so user understands OCR results
        if os.path.exists(proc_path):
            self.preview_image.source = proc_path
            self.preview_image.reload()
        else:
            self.preview_image.source = img_path
            self.preview_image.reload()

        # Load values into inputs
        if sys: self.sys_input.text = str(sys)
        if dia: self.dia_input.text = str(dia)
        if pulse: self.pulse_input.text = str(pulse)

        # Alert user if OCR failed completely
        if not sys or not dia:
            self.app.show_snackbar("OCR couldn't extract all numbers. Please input manually.")

    def load_manual_log(self):
        """
        Setup screen for purely manual logging with no OCR
        """
        self.image_path = None
        self.record_id = None
        self.sys_input.text = ""
        self.dia_input.text = ""
        self.pulse_input.text = ""
        self.note_input.text = ""
        self.preview_image.source = ""
        self.img_title.text = "Logging Manually (No Image Loaded)"
        self.app.show_snackbar("Please enter values manually.")

    def load_existing_record(self, record):
        """
        Setup screen to edit an existing logged record
        """
        self.record_id = record['id']
        self.image_path = None
        self.sys_input.text = str(record['systolic'])
        self.dia_input.text = str(record['diastolic'])
        self.pulse_input.text = str(record['pulse']) if record['pulse'] is not None else ""
        self.note_input.text = record['note'] or ""
        self.preview_image.source = ""
        self.img_title.text = f"Editing Record from {record['timestamp']}"

    def save_record(self, *args):
        # Validate inputs
        sys_str = self.sys_input.text.strip()
        dia_str = self.dia_input.text.strip()
        pulse_str = self.pulse_input.text.strip()
        note = self.note_input.text.strip()

        if not sys_str or not dia_str:
            self.app.show_snackbar("Error: Systolic and Diastolic values are required.")
            return

        try:
            sys = int(sys_str)
            dia = int(dia_str)
            pulse = int(pulse_str) if pulse_str else None
        except ValueError:
            self.app.show_snackbar("Error: Numbers must be valid integers.")
            return

        # Simple sanity check
        if not (40 <= sys <= 280) or not (30 <= dia <= 180):
            self.app.show_snackbar("Error: Unrealistic blood pressure values entered.")
            return

        if self.record_id:
            # Updating existing record
            orig_record = self.app.db.get_record(self.record_id)
            success = self.app.db.update_record(
                self.record_id, sys, dia, pulse, orig_record['timestamp'], note
            )
            msg = "Record updated successfully."
        else:
            # Adding new record
            self.app.db.add_record(sys, dia, pulse, note=note)
            success = True
            msg = "Record saved successfully."

        if success:
            self.app.show_snackbar(msg)
            # Update Dashboard
            self.app.dashboard.update_dashboard()
            # Return to main panel
            self.go_back()
        else:
            self.app.show_snackbar("Database Save Failed.")

    def go_back(self, *args):
        self.app.root.current = 'main'


class HistoryScreen(MDBoxLayout):
    """
    History View panel containing:
    - Navigation headers to toggle: Daily list, Weekly chart, Monthly statistics, Yearly stats
    - Custom Canvas Line Chart for visual trends
    - List of entries allowing deletion and manual edit.
    """
    def __init__(self, app_ref, **kwargs):
        super(HistoryScreen, self).__init__(**kwargs)
        self.app = app_ref
        self.orientation = 'vertical'
        self.spacing = dp(5)
        self.padding = dp(10)
        self.current_tab = "daily" # Options: daily, weekly, monthly, yearly
        self.selected_date = datetime.now()
        self.build_ui()

    def build_ui(self):
        self.clear_widgets()

        # 1. Period Selector Buttons
        tabs_box = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(5))
        
        self.tab_buttons = {}
        periods = [("daily", "DAILY"), ("weekly", "WEEKLY"), ("monthly", "MONTHLY"), ("yearly", "YEARLY")]
        
        for key, title in periods:
            # High Contrast Toggle
            btn = MDFillRoundFlatButton(
                text=title,
                size_hint_x=0.25,
                on_release=lambda x, k=key: self.switch_tab(k)
            )
            tabs_box.add_widget(btn)
            self.tab_buttons[key] = btn
            
        self.add_widget(tabs_box)

        # 2. Main content area (wrapped in scroll/box)
        self.content_area = MDBoxLayout(orientation='vertical', spacing=dp(10))
        self.add_widget(self.content_area)
        
        self.switch_tab("daily")

    def switch_tab(self, tab_key):
        self.current_tab = tab_key
        # Update colors on active tab
        for key, btn in self.tab_buttons.items():
            if key == tab_key:
                btn.md_bg_color = self.app.theme_cls.primary_color
                btn.text_color = (1, 1, 1, 1)
            else:
                btn.md_bg_color = get_color_from_hex("#E2E8F0")
                btn.text_color = (0.2, 0.2, 0.2, 1)
                
        self.update_content()

    def update_content(self):
        self.content_area.clear_widgets()

        if self.current_tab == "daily":
            self.render_daily_view()
        elif self.current_tab == "weekly":
            self.render_weekly_view()
        elif self.current_tab == "monthly":
            self.render_monthly_view()
        elif self.current_tab == "yearly":
            self.render_yearly_view()

    # RENDER VIEWS
    def render_daily_view(self):
        # Header showing current selected date and a DatePicker trigger
        header_box = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50), padding=dp(5))
        
        date_str = self.selected_date.strftime("%Y-%m-%d")
        date_lbl = MDLabel(
            text=f"Readings for: [b]{self.selected_date.strftime('%A, %b %d, %Y')}[/b]",
            markup=True,
            valign='middle'
        )
        header_box.add_widget(date_lbl)
        
        # Calendar Trigger
        cal_btn = MDIconButton(
            icon="calendar-month",
            on_release=self.show_date_picker
        )
        header_box.add_widget(cal_btn)
        self.content_area.add_widget(header_box)

        # Scrollable list of readings
        scroll = ScrollView()
        self.records_list = MDList()
        
        records = self.app.db.get_records_by_day(date_str)
        
        if not records:
            empty_lbl = MDLabel(
                text="No readings recorded for this day.",
                halign="center",
                theme_text_color="Secondary",
                size_hint_y=None,
                height=dp(100)
            )
            self.records_list.add_widget(empty_lbl)
        else:
            for r in records:
                sys = r['systolic']
                dia = r['diastolic']
                pulse = r['pulse']
                note = r['note'] or ""
                
                # Format time
                dt_str = r['timestamp'].split(" ")[1][:5] # HH:MM
                
                # Category color indicator
                range_bar = BPRangeBar()
                _, color = range_bar.get_bp_category(sys, dia)
                color_hex = color.hexval() if hasattr(color, 'hexval') else "#059669"
                
                # ThreeLineAvatarIconListItem
                item = ThreeLineAvatarIconListItem(
                    text=f"[b]{sys}/{dia}[/b] mmHg (Pulse: {pulse or '--'} bpm)",
                    secondary_text=f"Time: {dt_str} | Note: {note}",
                    tertiary_text="Tap to edit",
                    markup=True,
                    on_release=lambda x, rec=r: self.edit_record_dialog(rec)
                )
                
                # Left heart icon colored by category
                icon = IconLeftWidget(icon="heart-pulse", theme_text_color="Custom", icon_color=get_color_from_hex(color_hex))
                item.add_widget(icon)
                
                # Right delete button
                del_btn = IconRightWidget(
                    icon="delete", 
                    theme_text_color="Custom",
                    icon_color=get_color_from_hex("#EF4444"),
                    on_release=lambda x, rid=r['id']: self.confirm_delete_record(rid)
                )
                item.add_widget(del_btn)
                
                self.records_list.add_widget(item)
                
        scroll.add_widget(self.records_list)
        self.content_area.add_widget(scroll)

    def render_weekly_view(self):
        # Weekly averages & custom line chart of last 7 entries
        # Date range for last 7 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=6)
        
        date_range_str = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"
        
        header_lbl = MDLabel(
            text=f"Weekly Summary: [b]{date_range_str}[/b]",
            markup=True,
            size_hint_y=None,
            height=dp(25)
        )
        self.content_area.add_widget(header_lbl)

        # Get records in period
        records = self.app.db.get_records_for_period(
            start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
        )
        
        # Load stats
        stats = self.app.db.get_stats_for_period(
            start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
        )

        # Display Weekly averages cards
        stats_layout = MDBoxLayout(orientation='horizontal', spacing=dp(10), size_hint_y=None, height=dp(80))
        
        sys_avg = f"{stats['avg_sys']:.0f}" if stats and stats['avg_sys'] else "--"
        dia_avg = f"{stats['avg_dia']:.0f}" if stats and stats['avg_dia'] else "--"
        pulse_avg = f"{stats['avg_pulse']:.0f}" if stats and stats['avg_pulse'] else "--"
        
        sys_card = MDCard(orientation='vertical', padding=dp(10), elevation=2)
        sys_card.add_widget(MDLabel(text="SYS AVG", font_style="Caption", halign="center"))
        sys_card.add_widget(MDLabel(text=sys_avg, font_style="H5", bold=True, halign="center", theme_text_color="Primary"))
        
        dia_card = MDCard(orientation='vertical', padding=dp(10), elevation=2)
        dia_card.add_widget(MDLabel(text="DIA AVG", font_style="Caption", halign="center"))
        dia_card.add_widget(MDLabel(text=dia_avg, font_style="H5", bold=True, halign="center", theme_text_color="Primary"))

        pulse_card = MDCard(orientation='vertical', padding=dp(10), elevation=2)
        pulse_card.add_widget(MDLabel(text="PULSE AVG", font_style="Caption", halign="center"))
        pulse_card.add_widget(MDLabel(text=pulse_avg, font_style="H5", bold=True, halign="center", theme_text_color="Primary"))
        
        stats_layout.add_widget(sys_card)
        stats_layout.add_widget(dia_card)
        stats_layout.add_widget(pulse_card)
        self.content_area.add_widget(stats_layout)

        # Render visual line chart
        chart_card = MDCard(orientation='vertical', padding=dp(10), elevation=3, radius=[dp(12)])
        chart_card.add_widget(MDLabel(text="Systolic / Diastolic Line Chart", font_style="Subtitle2", theme_text_color="Secondary", size_hint_y=None, height=dp(20)))
        
        self.line_chart = BPLineChart(size_hint_y=1)
        self.line_chart.records = records
        chart_card.add_widget(self.line_chart)
        
        self.content_area.add_widget(chart_card)

    def render_monthly_view(self):
        curr_month_str = datetime.now().strftime("%Y-%m")
        header_lbl = MDLabel(
            text=f"Monthly Analysis: [b]{datetime.now().strftime('%B %Y')}[/b]",
            markup=True,
            size_hint_y=None,
            height=dp(25)
        )
        self.content_area.add_widget(header_lbl)

        # Retrieve Monthly summary stats
        stats = self.app.db.get_monthly_summary(curr_month_str)

        # Scrollview for monthly content
        scroll = ScrollView()
        body = MDBoxLayout(orientation='vertical', spacing=dp(15), padding=dp(5), size_hint_y=None)
        body.bind(minimum_height=body.setter('height'))

        if not stats:
            body.add_widget(MDLabel(text="No logs recorded this month yet.", halign="center", size_hint_y=None, height=dp(100)))
        else:
            # 1. Statistics Summary Card
            stats_card = MDCard(orientation='vertical', padding=dp(15), spacing=dp(10), elevation=2, size_hint_y=None, height=dp(210), radius=[dp(12)])
            stats_card.add_widget(MDLabel(text="MONTHLY METRICS", font_style="Overline", theme_text_color="Secondary"))
            
            avg_sys = f"{stats['avg_sys']:.1f}"
            avg_dia = f"{stats['avg_dia']:.1f}"
            peak_sys = stats['max_sys']
            peak_dia = stats['max_dia']
            min_sys = stats['min_sys']
            min_dia = stats['min_dia']
            
            grid = MDGridLayout(cols=2, spacing=dp(8))
            grid.add_widget(MDLabel(text=f"Average Systolic: [b]{avg_sys}[/b] mmHg", markup=True))
            grid.add_widget(MDLabel(text=f"Average Diastolic: [b]{avg_dia}[/b] mmHg", markup=True))
            grid.add_widget(MDLabel(text=f"Peak Systolic: [color=#DC2626][b]{peak_sys}[/b][/color]", markup=True))
            grid.add_widget(MDLabel(text=f"Peak Diastolic: [color=#DC2626][b]{peak_dia}[/b][/color]", markup=True))
            grid.add_widget(MDLabel(text=f"Minimum Systolic: [b]{min_sys}[/b]", markup=True))
            grid.add_widget(MDLabel(text=f"Minimum Diastolic: [b]{min_dia}[/b]", markup=True))
            
            stats_card.add_widget(grid)
            body.add_widget(stats_card)

            # 2. Charts comparison
            # Retrieve all records from this month to display on chart
            start_date = datetime.now().replace(day=1).strftime("%Y-%m-%d")
            end_date = (datetime.now().replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            records = self.app.db.get_records_for_period(start_date, end_date.strftime("%Y-%m-%d"))

            chart_card = MDCard(orientation='vertical', padding=dp(10), elevation=3, size_hint_y=None, height=dp(200), radius=[dp(12)])
            chart_card.add_widget(MDLabel(text="Monthly Line Chart", font_style="Subtitle2", theme_text_color="Secondary", size_hint_y=None, height=dp(20)))
            
            chart = BPLineChart()
            chart.records = records
            chart_card.add_widget(chart)
            body.add_widget(chart_card)

        scroll.add_widget(body)
        self.content_area.add_widget(scroll)

    def render_yearly_view(self):
        curr_year = datetime.now().strftime("%Y")
        header_lbl = MDLabel(
            text=f"Yearly Health Overview: [b]{curr_year}[/b]",
            markup=True,
            size_hint_y=None,
            height=dp(25)
        )
        self.content_area.add_widget(header_lbl)

        # Yearly analysis: fetch records for the whole year
        start_date = f"{curr_year}-01-01"
        end_date = f"{curr_year}-12-31"
        
        records = self.app.db.get_records_for_period(start_date, end_date)
        stats = self.app.db.get_stats_for_period(start_date, end_date)

        scroll = ScrollView()
        body = MDBoxLayout(orientation='vertical', spacing=dp(15), padding=dp(5), size_hint_y=None)
        body.bind(minimum_height=body.setter('height'))

        if not stats or stats['count'] == 0:
            body.add_widget(MDLabel(text="No logs recorded this year yet.", halign="center", size_hint_y=None, height=dp(100)))
        else:
            # Stats Card
            stats_card = MDCard(orientation='vertical', padding=dp(15), spacing=dp(10), elevation=2, size_hint_y=None, height=dp(180), radius=[dp(12)])
            stats_card.add_widget(MDLabel(text="YEARLY SUMMARY STATS", font_style="Overline", theme_text_color="Secondary"))
            
            grid = MDGridLayout(cols=2, spacing=dp(8))
            grid.add_widget(MDLabel(text=f"Yearly Average: [b]{stats['avg_sys']:.0f}/{stats['avg_dia']:.0f}[/b] mmHg", markup=True))
            grid.add_widget(MDLabel(text=f"Average Pulse: [b]{stats['avg_pulse']:.0f}[/b] bpm", markup=True))
            grid.add_widget(MDLabel(text=f"Peak BP: [color=#DC2626][b]{stats['max_sys']}/{stats['max_dia']}[/b][/color]", markup=True))
            grid.add_widget(MDLabel(text=f"Total Log Entries: [b]{stats['count']}[/b]", markup=True))
            
            stats_card.add_widget(grid)
            body.add_widget(stats_card)

            # Yearly Chart
            chart_card = MDCard(orientation='vertical', padding=dp(10), elevation=3, size_hint_y=None, height=dp(220), radius=[dp(12)])
            chart_card.add_widget(MDLabel(text="Yearly Trend (Max 30 Entries plotted)", font_style="Subtitle2", theme_text_color="Secondary", size_hint_y=None, height=dp(20)))
            
            chart = BPLineChart()
            # Feed max 30 records to avoid visual clutter
            chart.records = records[-30:] if len(records) > 30 else records
            chart_card.add_widget(chart)
            body.add_widget(chart_card)

        scroll.add_widget(body)
        self.content_area.add_widget(scroll)

    # Date picker callbacks
    def show_date_picker(self, *args):
        date_picker = MDDatePicker(
            year=self.selected_date.year,
            month=self.selected_date.month,
            day=self.selected_date.day
        )
        date_picker.bind(on_save=self.on_date_save)
        date_picker.open()

    def on_date_save(self, instance, value, date_range):
        self.selected_date = value
        self.update_content()

    # Edit & Delete logic
    def edit_record_dialog(self, record):
        # Open editor screen loaded with this record
        self.app.capture_screen.load_existing_record(record)
        self.app.root.current = 'capture'

    def confirm_delete_record(self, record_id):
        self.del_dialog = MDDialog(
            title="Delete Reading?",
            text="Are you sure you want to permanently delete this blood pressure reading? This cannot be undone.",
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda x: self.del_dialog.dismiss()),
                MDRaisedButton(
                    text="DELETE",
                    md_bg_color=get_color_from_hex("#EF4444"),
                    on_release=lambda x, rid=record_id: self.delete_record(rid)
                )
            ]
        )
        self.del_dialog.open()

    def delete_record(self, record_id):
        self.del_dialog.dismiss()
        if self.app.db.delete_record(record_id):
            self.app.show_snackbar("Reading deleted.")
            self.update_content()
            self.app.dashboard.update_dashboard()
        else:
            self.app.show_snackbar("Failed to delete record.")


class ReportScreen(MDBoxLayout):
    """
    Reports view allowing generation of customized medical PDFs,
    showing statistics, graphs, and triggering direct printing.
    """
    def __init__(self, app_ref, **kwargs):
        super(ReportScreen, self).__init__(**kwargs)
        self.app = app_ref
        self.orientation = 'vertical'
        self.spacing = dp(15)
        self.padding = dp(15)
        self.start_date = datetime.now() - timedelta(days=30)
        self.end_date = datetime.now()
        self.generated_pdf_path = None
        self.build_ui()

    def build_ui(self):
        self.clear_widgets()

        header = MDLabel(
            text="Medical Report Center",
            font_style="H5" if not self.app.high_contrast else "H4",
            theme_text_color="Primary",
            size_hint_y=None,
            height=dp(30)
        )
        self.add_widget(header)

        # Settings inputs card
        info_card = MDCard(
            orientation='vertical',
            padding=dp(15),
            spacing=dp(12),
            elevation=2,
            size_hint_y=None,
            height=dp(140),
            radius=[dp(12)]
        )
        
        info_card.add_widget(MDLabel(text="REPORT CONFIGURATION", font_style="Overline", theme_text_color="Secondary"))
        
        # User Name input (auto-saved)
        curr_name = self.app.db.get_setting("user_name", "User")
        self.name_input = MDTextField(
            text=curr_name,
            hint_text="Patient Full Name",
            helper_text="Included in the PDF header",
            helper_text_mode="on_focus"
        )
        self.name_input.bind(text=self.save_name)
        info_card.add_widget(self.name_input)
        self.add_widget(info_card)

        # Date range picker card
        range_card = MDCard(
            orientation='vertical',
            padding=dp(15),
            spacing=dp(12),
            elevation=2,
            size_hint_y=None,
            height=dp(150),
            radius=[dp(12)]
        )
        range_card.add_widget(MDLabel(text="DATE SELECT RANGE", font_style="Overline", theme_text_color="Secondary"))
        
        # Picker Row
        row = MDBoxLayout(orientation='horizontal', spacing=dp(10))
        
        self.start_btn = MDRaisedButton(
            text=f"Start: {self.start_date.strftime('%Y-%m-%d')}",
            on_release=lambda x: self.open_range_picker("start")
        )
        self.end_btn = MDRaisedButton(
            text=f"End: {self.end_date.strftime('%Y-%m-%d')}",
            on_release=lambda x: self.open_range_picker("end")
        )
        
        row.add_widget(self.start_btn)
        row.add_widget(self.end_btn)
        range_card.add_widget(row)
        self.add_widget(range_card)

        # Trigger Card
        self.pdf_btn = MDFillRoundFlatButton(
            text="GENERATE PDF HEALTH REPORT",
            icon="file-pdf-box",
            pos_hint={"center_x": 0.5},
            size_hint_x=0.9,
            height=dp(50),
            on_release=self.generate_report
        )
        self.add_widget(self.pdf_btn)

        # Print/Share Box (Visible only after generation)
        self.actions_box = MDBoxLayout(orientation='horizontal', spacing=dp(15), size_hint_y=None, height=dp(60))
        self.actions_box.opacity = 0 # Hidden initially
        
        self.share_btn = MDFillRoundFlatButton(
            text="SHARE REPORT",
            icon="share-variant",
            size_hint_x=0.5,
            on_release=self.share_report
        )
        
        self.print_btn = MDFillRoundFlatButton(
            text="PRINT WIRELESS",
            icon="printer",
            size_hint_x=0.5,
            on_release=self.print_report
        )
        
        self.actions_box.add_widget(self.share_btn)
        self.actions_box.add_widget(self.print_btn)
        self.add_widget(self.actions_box)

        # Bottom space
        self.add_widget(Spacer(size_hint_y=1))

    def save_name(self, instance, value):
        self.app.db.save_setting("user_name", value.strip())
        self.app.dashboard.welcome_label.text = f"Welcome back, [b]{value.strip()}[/b]"

    def open_range_picker(self, tag):
        current = self.start_date if tag == "start" else self.end_date
        picker = MDDatePicker(year=current.year, month=current.month, day=current.day)
        
        def on_save(instance, value, date_range):
            if tag == "start":
                self.start_date = value
                self.start_btn.text = f"Start: {value.strftime('%Y-%m-%d')}"
            else:
                self.end_date = value
                self.end_btn.text = f"End: {value.strftime('%Y-%m-%d')}"
                
        picker.bind(on_save=on_save)
        picker.open()

    def generate_report(self, *args):
        # Fetch records in period
        start_str = self.start_date.strftime("%Y-%m-%d")
        end_str = self.end_date.strftime("%Y-%m-%d")
        
        records = self.app.db.get_records_for_period(start_str, end_str)
        if not records:
            self.app.show_snackbar("Error: No records found for selected period.")
            return

        stats = self.app.db.get_stats_for_period(start_str, end_str)
        name = self.app.db.get_setting("user_name", "User")
        
        # Save to public Documents or Downloads directory for easy user access
        pub_dir = AndroidHelper.get_public_dir("Documents")
        filename = f"BP_Report_{self.start_date.strftime('%Y%m%d')}_{self.end_date.strftime('%Y%m%d')}.pdf"
        pdf_path = os.path.join(pub_dir, filename)

        try:
            self.generated_pdf_path = BPPdfGenerator.generate_report(
                records, pdf_path, user_name=name,
                date_range=f"{start_str} to {end_str}", stats=stats
            )
            self.app.show_snackbar(f"PDF Generated successfully in {filename}")
            # Show action buttons
            self.actions_box.opacity = 1
        except Exception as e:
            self.app.show_snackbar(f"Error generating PDF: {e}")

    def share_report(self, *args):
        if self.generated_pdf_path:
            AndroidHelper.share_pdf(self.generated_pdf_path)
        else:
            self.app.show_snackbar("Please generate a report first.")

    def print_report(self, *args):
        if self.generated_pdf_path:
            AndroidHelper.print_pdf(self.generated_pdf_path)
        else:
            self.app.show_snackbar("Please generate a report first.")


class SettingsScreen(MDBoxLayout):
    """
    Settings view containing theme configs, elderly high-contrast toggles, 
    and complete JSON/CSV import/export operations for data backup.
    """
    def __init__(self, app_ref, **kwargs):
        super(SettingsScreen, self).__init__(**kwargs)
        self.app = app_ref
        self.orientation = 'vertical'
        self.spacing = dp(15)
        self.padding = dp(15)
        self.build_ui()

    def build_ui(self):
        self.clear_widgets()

        header = MDLabel(
            text="Settings & Backup",
            font_style="H5" if not self.app.high_contrast else "H4",
            theme_text_color="Primary",
            size_hint_y=None,
            height=dp(30)
        )
        self.add_widget(header)

        # 1. Theme Configuration Card
        theme_card = MDCard(
            orientation='vertical',
            padding=dp(15),
            spacing=dp(10),
            elevation=2,
            size_hint_y=None,
            height=dp(130),
            radius=[dp(12)]
        )
        theme_card.add_widget(MDLabel(text="THEME & READABILITY", font_style="Overline", theme_text_color="Secondary"))
        
        # Row 1: Dark Mode Toggle
        row1 = MDBoxLayout(orientation='horizontal')
        row1.add_widget(MDLabel(text="Dark Mode Toggle", font_style="Body1"))
        dark_toggle = MDIconButton(
            icon="weather-night" if self.app.theme_cls.theme_style == "Dark" else "weather-sunny",
            on_release=self.toggle_dark_theme
        )
        row1.add_widget(dark_toggle)
        theme_card.add_widget(row1)

        # Row 2: High Contrast (Elderly friendly)
        row2 = MDBoxLayout(orientation='horizontal')
        row2.add_widget(MDLabel(text="High Contrast Mode", font_style="Body1"))
        contrast_toggle = MDIconButton(
            icon="checkbox-marked" if self.app.high_contrast else "checkbox-blank-outline",
            on_release=self.toggle_high_contrast
        )
        row2.add_widget(contrast_toggle)
        theme_card.add_widget(row2)

        self.add_widget(theme_card)

        # 2. Backup/Restore Card
        backup_card = MDCard(
            orientation='vertical',
            padding=dp(15),
            spacing=dp(12),
            elevation=2,
            size_hint_y=None,
            height=dp(230),
            radius=[dp(12)]
        )
        backup_card.add_widget(MDLabel(text="DATA STORAGE BACKUP & RESTORE", font_style="Overline", theme_text_color="Secondary"))
        
        # Row: Export Grid
        row_exp = MDBoxLayout(orientation='horizontal', spacing=dp(10))
        row_exp.add_widget(MDFillRoundFlatButton(
            text="EXPORT CSV",
            icon="file-excel",
            size_hint_x=0.5,
            on_release=self.export_csv
        ))
        row_exp.add_widget(MDFillRoundFlatButton(
            text="EXPORT JSON",
            icon="file-code",
            size_hint_x=0.5,
            on_release=self.export_json
        ))
        backup_card.add_widget(row_exp)

        # Row: Import Grid
        row_imp = MDBoxLayout(orientation='horizontal', spacing=dp(10))
        row_imp.add_widget(MDFillRoundFlatButton(
            text="IMPORT CSV",
            icon="import",
            size_hint_x=0.5,
            on_release=self.import_csv
        ))
        row_imp.add_widget(MDFillRoundFlatButton(
            text="IMPORT JSON",
            icon="database-import",
            size_hint_x=0.5,
            on_release=self.import_json
        ))
        backup_card.add_widget(row_imp)
        
        self.add_widget(backup_card)

        # 3. Danger Zone Card (Database Wipe)
        danger_card = MDCard(
            orientation='vertical',
            padding=dp(15),
            spacing=dp(10),
            elevation=2,
            size_hint_y=None,
            height=dp(110),
            radius=[dp(12)],
            line_color=[1,0,0,0.3]
        )
        danger_card.add_widget(MDLabel(text="DANGER ZONE", font_style="Overline", theme_text_color="Error"))
        
        wipe_btn = MDRaisedButton(
            text="WIPE DATABASE ENTRIES",
            icon="alert",
            md_bg_color=get_color_from_hex("#DC2626"),
            pos_hint={"center_x": 0.5},
            size_hint_x=0.9,
            on_release=self.confirm_wipe_db
        )
        danger_card.add_widget(wipe_btn)
        self.add_widget(danger_card)

        # Spacer
        self.add_widget(Spacer(size_hint_y=1))

    # Toggles
    def toggle_dark_theme(self, *args):
        if self.app.theme_cls.theme_style == "Dark":
            self.app.theme_cls.theme_style = "Light"
        else:
            self.app.theme_cls.theme_style = "Dark"
        
        self.app.db.save_setting("theme_style", self.app.theme_cls.theme_style)
        self.build_ui()

    def toggle_high_contrast(self, *args):
        self.app.high_contrast = not self.app.high_contrast
        self.app.db.save_setting("high_contrast", "1" if self.app.high_contrast else "0")
        
        # Rebuild whole UI to reflect text size adjustments
        self.app.dashboard.build_ui()
        self.app.history.build_ui()
        self.app.report.build_ui()
        self.build_ui()

    # Backups
    def export_csv(self, *args):
        pub_dir = AndroidHelper.get_public_dir("Documents")
        filepath = os.path.join(pub_dir, "BP_Records_Backup.csv")
        try:
            count = self.app.db.export_to_csv(filepath)
            self.app.show_snackbar(f"Backup Successful! {count} entries exported to {filepath}")
        except Exception as e:
            self.app.show_snackbar(f"CSV Export Error: {e}")

    def export_json(self, *args):
        pub_dir = AndroidHelper.get_public_dir("Documents")
        filepath = os.path.join(pub_dir, "BP_Records_Backup.json")
        try:
            count = self.app.db.export_to_json(filepath)
            self.app.show_snackbar(f"Backup Successful! {count} entries exported to {filepath}")
        except Exception as e:
            self.app.show_snackbar(f"JSON Export Error: {e}")

    def import_csv(self, *args):
        # On PC we launch Tkinter file dialog, on Android we tell user to put the file in Documents
        if not AndroidHelper.is_android:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            filepath = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
            root.destroy()
            
            if filepath:
                self._run_csv_import(filepath)
        else:
            # For Android, we scan standard public Documents folder for direct restoration
            pub_dir = AndroidHelper.get_public_dir("Documents")
            filepath = os.path.join(pub_dir, "BP_Records_Backup.csv")
            if os.path.exists(filepath):
                self._run_csv_import(filepath)
            else:
                self.app.show_snackbar("Please place 'BP_Records_Backup.csv' in your Documents folder.")

    def _run_csv_import(self, filepath):
        try:
            count = self.app.db.import_from_csv(filepath)
            self.app.show_snackbar(f"Restored {count} records from CSV successfully!")
            self.app.dashboard.update_dashboard()
        except Exception as e:
            self.app.show_snackbar(f"Import failed: {e}")

    def import_json(self, *args):
        if not AndroidHelper.is_android:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            filepath = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
            root.destroy()
            
            if filepath:
                self._run_json_import(filepath)
        else:
            pub_dir = AndroidHelper.get_public_dir("Documents")
            filepath = os.path.join(pub_dir, "BP_Records_Backup.json")
            if os.path.exists(filepath):
                self._run_json_import(filepath)
            else:
                self.app.show_snackbar("Please place 'BP_Records_Backup.json' in your Documents folder.")

    def _run_json_import(self, filepath):
        try:
            count = self.app.db.import_from_json(filepath)
            self.app.show_snackbar(f"Restored {count} records from JSON successfully!")
            self.app.dashboard.update_dashboard()
        except Exception as e:
            self.app.show_snackbar(f"Import failed: {e}")

    # Wipe database
    def confirm_wipe_db(self, *args):
        self.wipe_dialog = MDDialog(
            title="Wipe Entire Database?",
            text="This will delete all your blood pressure entries permanently. There is no backup undo.",
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda x: self.wipe_dialog.dismiss()),
                MDRaisedButton(
                    text="CONFIRM WIPE",
                    md_bg_color=get_color_from_hex("#DC2626"),
                    on_release=self.wipe_database
                )
            ]
        )
        self.wipe_dialog.open()

    def wipe_database(self, *args):
        self.wipe_dialog.dismiss()
        records = self.app.db.get_all_records()
        for r in records:
            self.app.db.delete_record(r['id'])
        
        self.app.show_snackbar("Database cleared.")
        self.app.dashboard.update_dashboard()
