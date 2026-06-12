import sqlite3
import os
import csv
import json
from datetime import datetime

class BPDatabase:
    def __init__(self, db_path=None):
        if db_path is None:
            # Check if running in Kivy environment to place db in user_data_dir
            try:
                from kivy.app import App
                app = App.get_running_app()
                if app and app.user_data_dir:
                    db_dir = app.user_data_dir
                else:
                    db_dir = "."
            except ImportError:
                db_dir = "."
            
            db_path = os.path.join(db_dir, "bp_logger.db")
            
        self.db_path = os.path.abspath(db_path)
        # Ensure parent directory exists
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Records table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    systolic INTEGER NOT NULL,
                    diastolic INTEGER NOT NULL,
                    pulse INTEGER,
                    note TEXT
                )
            """)
            # Settings table (for theme, user info, etc.)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()

    # Record CRUD
    def add_record(self, systolic, diastolic, pulse, timestamp=None, note=""):
        if not timestamp:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO records (timestamp, systolic, diastolic, pulse, note)
                VALUES (?, ?, ?, ?, ?)
            """, (timestamp, int(systolic), int(diastolic), int(pulse) if pulse is not None else None, note))
            conn.commit()
            return cursor.lastrowid

    def update_record(self, record_id, systolic, diastolic, pulse, timestamp, note=""):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE records
                SET timestamp = ?, systolic = ?, diastolic = ?, pulse = ?, note = ?
                WHERE id = ?
            """, (timestamp, int(systolic), int(diastolic), int(pulse) if pulse is not None else None, note, record_id))
            conn.commit()
            return cursor.rowcount > 0

    def delete_record(self, record_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM records WHERE id = ?", (record_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_record(self, record_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM records WHERE id = ?", (record_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_records(self, order="DESC"):
        # Order can be ASC or DESC
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM records ORDER BY timestamp {order}")
            return [dict(row) for row in cursor.fetchall()]

    # Query Views
    def get_records_by_day(self, date_str):
        # date_str: "YYYY-MM-DD"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM records 
                WHERE timestamp LIKE ? 
                ORDER BY timestamp DESC
            """, (f"{date_str}%",))
            return [dict(row) for row in cursor.fetchall()]

    def get_records_for_period(self, start_date, end_date):
        # start_date & end_date: "YYYY-MM-DD"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM records 
                WHERE date(timestamp) BETWEEN date(?) AND date(?)
                ORDER BY timestamp ASC
            """, (start_date, end_date))
            return [dict(row) for row in cursor.fetchall()]

    def get_stats_for_period(self, start_date, end_date):
        # Returns aggregates (average, min, max) for a date range
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(id) as count,
                    AVG(systolic) as avg_sys,
                    MIN(systolic) as min_sys,
                    MAX(systolic) as max_sys,
                    AVG(diastolic) as avg_dia,
                    MIN(diastolic) as min_dia,
                    MAX(diastolic) as max_dia,
                    AVG(pulse) as avg_pulse,
                    MIN(pulse) as min_pulse,
                    MAX(pulse) as max_pulse
                FROM records
                WHERE date(timestamp) BETWEEN date(?) AND date(?)
            """, (start_date, end_date))
            row = cursor.fetchone()
            return dict(row) if row and row['count'] > 0 else None

    def get_monthly_summary(self, year_month_str):
        # year_month_str: "YYYY-MM"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(id) as count,
                    AVG(systolic) as avg_sys,
                    MIN(systolic) as min_sys,
                    MAX(systolic) as max_sys,
                    AVG(diastolic) as avg_dia,
                    MIN(diastolic) as min_dia,
                    MAX(diastolic) as max_dia,
                    AVG(pulse) as avg_pulse
                FROM records
                WHERE timestamp LIKE ?
            """, (f"{year_month_str}%",))
            row = cursor.fetchone()
            return dict(row) if row and row['count'] > 0 else None

    # CSV/JSON Import & Export
    def export_to_csv(self, filepath):
        records = self.get_all_records(order="ASC")
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'timestamp', 'systolic', 'diastolic', 'pulse', 'note'])
            for r in records:
                writer.writerow([r['id'], r['timestamp'], r['systolic'], r['diastolic'], r['pulse'], r['note']])
        return len(records)

    def export_to_json(self, filepath):
        records = self.get_all_records(order="ASC")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(records, f, indent=4)
        return len(records)

    def import_from_csv(self, filepath):
        count = 0
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            with self.get_connection() as conn:
                cursor = conn.cursor()
                for row in reader:
                    ts = row.get('timestamp')
                    sys = row.get('systolic')
                    dia = row.get('diastolic')
                    pulse = row.get('pulse')
                    note = row.get('note', '')
                    
                    if ts and sys and dia:
                        p = int(pulse) if (pulse and pulse.strip() and pulse.lower() != 'none') else None
                        cursor.execute("""
                            INSERT INTO records (timestamp, systolic, diastolic, pulse, note)
                            VALUES (?, ?, ?, ?, ?)
                        """, (ts, int(sys), int(dia), p, note))
                        count += 1
                conn.commit()
        return count

    def import_from_json(self, filepath):
        count = 0
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            with self.get_connection() as conn:
                cursor = conn.cursor()
                for item in data:
                    ts = item.get('timestamp')
                    sys = item.get('systolic')
                    dia = item.get('diastolic')
                    pulse = item.get('pulse')
                    note = item.get('note', '')
                    
                    if ts and sys and dia:
                        p = int(pulse) if pulse is not None else None
                        cursor.execute("""
                            INSERT INTO records (timestamp, systolic, diastolic, pulse, note)
                            VALUES (?, ?, ?, ?, ?)
                        """, (ts, int(sys), int(dia), p, note))
                        count += 1
                conn.commit()
        return count

    # Settings Accessors
    def save_setting(self, key, value):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """, (key, str(value)))
            conn.commit()

    def get_setting(self, key, default=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row['value'] if row else default
