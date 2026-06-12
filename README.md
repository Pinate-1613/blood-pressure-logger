# Blood Pressure Scan & Log Web Application (PWA)

A client-side, offline-first Progressive Web Application (PWA) that allows users to scan digital blood pressure monitors via their device camera, extract values locally using Javascript-based OCR, store records in an on-device database, and compile printable medical reports with wireless printing support.

This application runs directly in the browser of any mobile or desktop device (Android, iOS, Windows, macOS) without compilation, installations, or cloud database servers.

---

## Key Features
* **Browser-Native Camera**: Uses HTML5 Media Capture to launch your phone's native camera or gallery picker directly.
* **On-Device OCR Engine**: Utilizes **Tesseract.js** in a client-side Web Worker to scan digital LCD displays offline.
* **IndexedDB Local Storage**: Stores reading entries securely on the user's device. No cloud storage, no account registration.
* **Chart.js Visual Trend**: Generates responsive, medical-style line graphs for Daily, Weekly, Monthly, and Yearly readings.
* **Instant Wireless Printing**: Combines browser `window.print()` with custom CSS print overrides, allowing instant formatting and printing via Apple AirPrint or Android Print.
* **Elderly Readable Theme**: Large typography, clean button grids, and a high-contrast mode button suited for older users.
* **JSON/CSV Backups**: Instant local file backup downloads and restoration file pickers.

---

## File Structure

```text
BPlogger/
├── index.html   # Main application structure, layouts & dialogs
├── style.css    # Typography, dark themes, high-contrast, & print stylesheets
├── app.js       # IndexedDB manager, Chart.js trends, & Tesseract.js OCR engine
└── README.md    # User manual & developer guide
```

---

## Database Schema (IndexedDB)

The app initializes an offline database store named `bpAppDB` containing two object stores:

### 1. `readings` Store
* **KeyPath**: `id` (Auto-Incrementing integer)
* **Index**: `timestamp` (For date range filtration)

| Field | Data Type | Description |
| :--- | :--- | :--- |
| `id` | `Number` | Unique record ID |
| `timestamp` | `String` | Format: `YYYY-MM-DD HH:MM:SS` |
| `systolic` | `Number` | Systolic pressure (mmHg) |
| `diastolic` | `Number` | Diastolic pressure (mmHg) |
| `pulse` | `Number` | Heart rate (bpm) |
| `note` | `String` | Optional patient notes |

### 2. `config` Store
* **KeyPath**: `key` (String)
* Stores settings such as `user_name`, `theme_style` (light/dark), and `high_contrast` (1/0).

---

## Local Execution Instructions

Because modern browsers enforce **CORS security policies** on local file protocols (`file://`), loading Web Workers (used by Tesseract.js) requires the app to be served from a local static file server.

### 1. Start a Local Server
Open your terminal inside the project directory and run:
```bash
# Python 3
python -m http.server 8000
```

### 2. Open the Browser
Open your browser and navigate to:
```text
http://localhost:8000
```
The application is ready to test, run, and log!

---

## Deploying to Android & iOS

To access the app on your phone, you can host these static files for free.

### Option 1: GitHub Pages (Easiest Cloud Setup)
1. Push `index.html`, `style.css`, and `app.js` to a public repository on GitHub.
2. Go to your repository **Settings** -> **Pages**.
3. Under **Build and deployment**, select **Deploy from a branch** and set it to `main` (or `master`). Click **Save**.
4. GitHub will give you a public URL (e.g., `https://yourusername.github.io/repository/`). Open this link on your iPhone or Android!

### Option 2: Local Network Sharing
1. Start the Python server on your computer: `python -m http.server 8000`.
2. Find your computer's local IP address (run `ipconfig` on Windows or `ifconfig` on macOS/Linux). E.g., `192.168.1.15`.
3. Open your mobile browser and enter: `http://192.168.1.15:8000`.

---

## Client-Side OCR Algorithm

To achieve greater than 95% accuracy on digital blood pressure displays, `app.js` performs client-side pixel manipulation:

1. **Canvas Resizing**: Downscales image uploads to a width of 400px to keep OCR parsing fast.
2. **Linear Histogram Contrast Stretching**: Automatically stretches the grayscaled pixels between the minimum and maximum detected intensities to make faded LCD digits stand out.
3. **Adaptive Thresholding Binarization**: Converts the pixels into stark black digits on a white background, cleaning up shadows and lighting glares.
4. **Tesseract.js Whitelist Config**: Configures the OCR worker with `tessedit_char_whitelist` set to `0123456789/ \n\r` to prevent letter hallucination.
5. **Safe Ratio Heuristics**: Parses extracted integers. Assigns the largest number to Systolic, the second to Diastolic, and the lowest to Pulse (matching standard human biology $SYS > DIA > Pulse$).
