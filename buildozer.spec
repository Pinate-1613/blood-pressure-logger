[app]

# (str) Title of your application
title = BP Logger

# (str) Package name
package.name = bplogger

# (str) Package domain (needed for android packaging)
package.domain = org.kivy

# (str) Source code directory
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,xml

# (list) List of directory to exclude
source.exclude_dirs = tests, bin, .venv, .git, .gemini

# (str) Application version
version = 1.0.0

# (list) Application requirements
# comma separated e.g. requirements = sqlite3,kivy
requirements = python3,kivy,kivymd,numpy,opencv,reportlab,pyjnius,plyer

# (str) Supported orientations (one of landscape, sensorLandscape, portrait or all)
orientation = portrait

# (bool) Use fullscreen or not
fullscreen = 0

# =============================================================================
# Android specific configurations
# =============================================================================

# (list) Permissions to request
android.permissions = CAMERA, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, INTERNET

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API your APK will support.
android.minapi = 21

# (str) Android SDK version to use
android.sdk = 33

# (bool) Enable AndroidX support
android.enable_androidx = True

# (list) Android Gradle dependencies
# We add print support library to enable Android PrintHelper
android.gradle_dependencies = androidx.print:print:1.0.0

# (str) Android additional resource directory
# Links our custom xml/file_paths.xml resource directory into the build
android.resource_dir = %(source.dir)s/res

# (list) The Android archs to build for, choices: armeabi-v7a, arm64-v8a, x86, x86_64
# arm64-v8a is the standard target for modern devices. armeabi-v7a is for older 32-bit devices.
android.archs = arm64-v8a

# (bool) Grant all permissions at install time (for debug builds on older Androids)
android.accept_sdk_license = True

# (str) Logcat filter to use
android.logcat_filters = *:S python:D

# =============================================================================
# Buildozer configurations
# =============================================================================

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1
