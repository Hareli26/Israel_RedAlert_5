# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for RedAlertIDF macOS .app bundle

import os
HERE = os.path.abspath(SPECPATH)

block_cipher = None

a = Analysis(
    [os.path.join(HERE, 'red_alert.py')],
    pathex=[HERE],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.QtNetwork',
        'PyQt5.QtWebEngineWidgets',
        'PyQt5.QtWebEngineCore',
        'PyQt5.QtWebEngine',
        'PyQt5.QtWebChannel',
        'PyQt5.sip',
        'requests',
        'requests.adapters',
        'requests.auth',
        'requests.cookies',
        'requests.exceptions',
        'requests.models',
        'requests.sessions',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',
        'sqlite3',
        'json',
        'hashlib',
        'threading',
        'wave',
        'struct',
        'math',
        'subprocess',
        'webbrowser',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'ctypes',
        'winreg',
        'winsound',
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'IPython',
        'jupyter',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RedAlertIDF',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(HERE, 'RedAlertIDF.icns'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='RedAlertIDF',
)

app = BUNDLE(
    coll,
    name='RedAlertIDF.app',
    icon=os.path.join(HERE, 'RedAlertIDF.icns'),
    bundle_identifier='com.redalert.idf',
    version='5.3.0',
    info_plist={
        'CFBundleName':              'RedAlertIDF',
        'CFBundleDisplayName':       'התרעות צבע אדום',
        'CFBundleIdentifier':        'com.redalert.idf',
        'CFBundleVersion':           '5.3.0',
        'CFBundleShortVersionString':'5.3.0',
        'CFBundleExecutable':        'RedAlertIDF',
        'CFBundleIconFile':          'RedAlertIDF',
        'NSPrincipalClass':          'NSApplication',
        'NSHighResolutionCapable':   True,
        'NSRequiresAquaSystemAppearance': False,
        'NSMicrophoneUsageDescription': '',
        'NSAppTransportSecurity':    {'NSAllowsArbitraryLoads': True},
        'LSMinimumSystemVersion':    '12.0',
        'LSApplicationCategoryType': 'public.app-category.utilities',
        'LSUIElement':               False,
        'NSHumanReadableCopyright':  'RedAlertIDF 5.3.0',
    },
)
