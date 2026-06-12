# Android Blood Pressure Logger & Scanner

An offline-first, privacy-respecting Android application that allows users to capture a photo of a digital blood pressure monitor, automatically extract the readings using local computer vision (OpenCV), manage records in a local SQLite database, view medical trend charts, and export printable PDF reports with wireless printing support.

---

## Table of Contents
1. [Key Features](#key-features)
2. [Folder Structure](#folder-structure)
3. [Database Schema](#database-schema)
4. [Local Desktop Setup & Execution](#local-desktop-setup--execution)
5. [Android Compilation & Deployment Guide](#android-compilation--deployment-guide)
   - [Buildozer Prerequisites](#buildozer-prerequisites)
   - [APK Generation Process](#apk-generation-process)
   - [USB Debugging & Installation](#usb-debugging--installation)
   - [Troubleshooting Common Build Issues](#troubleshooting-common-build-issues)
6. [Local OCR Pre-processing & Algorithm](#local-ocr-pre-processing--algorithm)
7. [User Manual](#user-manual)
   - [Reading the Screens](#reading-the-screens)
   - [Elderly Accessibility & High-Contrast Mode](#elderly-accessibility--high-contrast-mode)
   - [Backup, Export, & Restore](#backup-export--restore)

---

## Key Features
* **Offline OCR Scanner**: Converts images from the device camera or gallery into numeric readings entirely on-device (zero cloud calls, zero internet dependency).
* **Robust Local Storage**: Readings are recorded in a SQLite database, allowing notes, dates, and times to be logged securely.
* **Aggregations & Trends**: Daily logs list, Weekly line charts, Monthly statistics (Min, Max, Averages), and Yearly long-term trend lines.
* **Vector PDF Reports**: Generates professional, crisp vector-based medical charts and tables in a printable PDF.
* **Wireless Printing**: Integrates with the native Android Print Framework via intent, allowing direct Wi-Fi printing.
* **Elderly Friendly**: Built with oversized buttons, high-contrast display options, and clean navigation layouts.

---

## Folder Structure

```text
BPlogger/
├── main.py                # App entrypoint, Screen Manager & navigation flow
├── database.py            # SQLite database schema, CRUD operations & backups
├── ocr_engine.py          # OpenCV preprocessing & 7-segment digit classification
├── chart_widgets.py       # Custom Kivy canvas widgets (Line charts & range bars)
├── pdf_generator.py       # ReportLab PDF compiler for medical print logs
├── android_helper.py      # Native Android bridge (Intents, Pyjnius, print)
├── requirements.txt       # Local desktop environment requirements
├── buildozer.spec         # Android packaging specifications
└── res/
    └── xml/
        └── file_paths.xml # File Provider configuration for secure Android file-sharing
```

---

## Database Schema

The app uses two main SQLite tables inside `bp_logger.db`:

### 1. `records` Table
Stores individual reading entries.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Unique identifier |
| `timestamp` | `TEXT` | `NOT NULL` | Format: `YYYY-MM-DD HH:MM:SS` |
| `systolic` | `INTEGER` | `NOT NULL` | Systolic reading (mmHg) |
| `diastolic` | `INTEGER` | `NOT NULL` | Diastolic reading (mmHg) |
| `pulse` | `INTEGER` | `NULLABLE` | Heart rate (bpm) |
| `note` | `TEXT` | `NULLABLE` | Short note (e.g., "took medicine") |

### 2. `settings` Table
Stores user preferences, themes, and profile metadata.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `key` | `TEXT` | `PRIMARY KEY` | Setting name (e.g., `user_name`, `theme_style`) |
| `value` | `TEXT` | | Stored setting value as string |

---

## Local Desktop Setup & Execution

You can run, test, and debug the complete codebase on Windows, macOS, or Linux. On desktop, camera capture is mocked via the computer's webcam (using OpenCV) and file selection falls back to the native file dialog.

### 1. Prerequisites
Install **Python 3.8 to 3.11** on your system.

### 2. Installation
Open a terminal in the project directory and run:
```bash
pip install -r requirements.txt
```

### 3. Run the App
Launch the app with:
```bash
python main.py
```
*Note: A desktop window of dimensions `400 x 720` will render, simulating a mobile phone viewport.*

---

## Android Compilation & Deployment Guide

To build the project into an Android APK, we use **Buildozer** inside a Linux environment (Ubuntu is highly recommended). Windows users can compile using **WSL (Windows Subsystem for Linux)**.

### Buildozer Prerequisites

Buildozer requires specific dependencies to compile Python and C++ modules (such as NumPy and OpenCV) for the Android ARM64 architecture:

```bash
# Update package lists
sudo apt update

# Install compilation libraries
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip autoconf libtool pkg-config \
    zlib1g-dev libncurses5-dev libssl-dev cmake libffi-dev libgdbm-dev \
    build-essential python3-dev
```

### APK Generation Process

Follow these steps to generate a debug or release APK:

1. **Install Buildozer**:
   ```bash
   pip3 install --user buildozer
   ```
2. **Compile the App**:
   Navigate to the project source directory (containing `buildozer.spec`) and run:
   ```bash
   buildozer android debug
   ```
   *Note: The first build will take 15–30 minutes as it downloads the Android SDK, NDK, compiles Python for Android, and builds the libraries (OpenCV, NumPy). Subsequent builds will take less than a minute.*
3. **Locate the APK**:
   Once finished, the generated APK will be available in the `bin/` subfolder:
   `bin/bplogger-1.0.0-arm64-v8a-debug.apk`

---

### USB Debugging & Installation

1. **Enable Developer Mode**: On your Android device, go to `Settings` -> `About Phone` -> tap `Build Number` 7 times.
2. **Enable USB Debugging**: Go to `Settings` -> `System` -> `Developer Options` and toggle `USB Debugging` ON.
3. **Auto-Install via Buildozer**:
   Connect your phone to your computer via USB and execute:
   ```bash
   buildozer android deploy run
   ```
   This will automatically push the compiled APK, install it on your device, and open the app.
4. **View Android Logs**:
   To monitor the app logs (like python `print` statements or errors) in real time:
   ```bash
   buildozer android logcat
   ```

---

### Troubleshooting Common Build Issues

* **Werror / C++ compilation errors**:
  * *Cause*: Incompatibilities between OpenCV/NumPy C extensions and modern NDK versions.
  * *Fix*: The `buildozer.spec` included in this package specifies `android.sdk = 33` and `android.api = 33` which matches stable compiler platforms. If errors occur, run `buildozer clean` to wipe build caches and recompile.
* **`FileUriExposedException`**:
  * *Cause*: Attempting to share file URIs directly with intents on Android 7.0 (API 24) or higher.
  * *Fix*: This app uses `androidx.core.content.FileProvider` combined with the configuration in `res/xml/file_paths.xml` to share file paths securely.
* **Storage Permission Denied (Android 13+)**:
  * *Cause*: Android 13 deprecated `READ_EXTERNAL_STORAGE` and split it into specific media scopes.
  * *Fix*: The `android_helper.py` dynamically checks the API version and requests `android.permission.READ_MEDIA_IMAGES` on API 33+ devices.

---

## Local OCR Pre-processing & Algorithm

To avoid massive PyTorch binaries (EasyOCR) or complex C++ Tesseract compilations, the application uses an optimized OpenCV pipeline:

1. **Adaptive Thresholding**: Converts the LCD screen into a high-contrast binary grid (white digits on a black background), compensating for shadow variations and glare.
2. **Contour Extraction**: Segments digit regions based on expected bounding box height (4%–35% of image height) and aspect ratio (0.2–0.95).
3. **Vertical Centroid Clustering**: Group digits vertically into 3 distinct rows matching the standard layout:
   * Row 1 (Top) -> Systolic
   * Row 2 (Middle) -> Diastolic
   * Row 3 (Bottom) -> Pulse
4. **Programmatic Template Matching**: Compares segmented digits against pre-rendered LCD and sans-serif digit templates.
5. **Medical Range Heuristic**: If vertical clustering fails or is ambiguous, the engine maps the highest number to Systolic, the second to Diastolic, and the lowest to Pulse (matching human biological ratios: $SYS > DIA > Pulse$).

---

## User Manual

### Reading the Screens

#### Dashboard
* Displays your last entry in large digits.
* The color-coded **Range Bar** places an indicator dot along the 5 AHA zones:
  * **Normal** (Green)
  * **Elevated** (Yellow)
  * **High Stage 1** (Orange)
  * **High Stage 2** (Red)
  * **Crisis** (Dark Crimson)

#### History Tab
* **Daily**: View list of readings. Tap any item to edit the note/value, or tap the delete icon to remove it. Use the Calendar button to switch days.
* **Weekly**: Renders a line chart displaying trend lines for Systolic and Diastolic values over the last 7 days.
* **Monthly/Yearly**: Displays maximum, minimum, and average statistics alongside full-period line charts.

#### Capture Tab
* Displays the preprocessed scanner frame. If OCR makes a mistake due to bad lighting, you can tap any input field to correct it before saving.

---

## Elderly Accessibility & High-Contrast Mode

The application provides accessibility support for elderly users:
1. Navigate to the **Settings** tab.
2. Toggle **High Contrast Mode** ON.
3. This will immediately adjust the application UI to use:
   * Extra-large typography.
   * Prominent bold texts.
   * High-contrast button outlines.
   * High-contrast dark backgrounds.

---

## Backup, Export, & Restore

All records remain exclusively on the local device. To back up or transfer your records:
1. Navigate to **Settings**.
2. Tap **Export CSV** or **Export JSON**.
3. The app will save the files to your device's public **Documents** folder.
4. To restore records on a new device, place the exported file (`BP_Records_Backup.json` or `BP_Records_Backup.csv`) in the new device's public **Documents** folder and tap **Import JSON** or **Import CSV** in the settings.
"# blood-pressure-logger" 
