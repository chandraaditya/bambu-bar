"""
Setup script for creating the BambuStatusMenuApp macOS application bundle.
"""

from setuptools import setup

APP_NAME = "BambuStatusMenuApp"
APP_SCRIPT = 'bambu_menubar.py'
VERSION = "0.1.0"

DATA_FILES = []
OPTIONS = {
    # 'argv_emulation': True, # Disabled as it seems to cause Carbon framework error
    'packages': ['paho', 'rumps'], # Explicitly include paho-mqtt and rumps
    'includes': ['jaraco'],       # Force include the jaraco namespace
    'plist': {
        'CFBundleName': APP_NAME,
        'CFBundleDisplayName': APP_NAME,
        'CFBundleGetInfoString': "Bambu Lab Printer Status Menu Bar App",
        'CFBundleIdentifier': f"com.yourdomain.{APP_NAME.lower()}", # Replace with your actual domain/identifier
        'CFBundleVersion': VERSION,
        'CFBundleShortVersionString': VERSION,
        'NSHumanReadableCopyright': u"Copyright © 2024 Your Name. All rights reserved.", # Replace Your Name
        'LSUIElement': True, # Makes it a background-only agent app (no Dock icon)
    },
    'iconfile': 'icon.icns' # Use the generated icon file
}

setup(
    name=APP_NAME,
    app=[APP_SCRIPT],
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
) 