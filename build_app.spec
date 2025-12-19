# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for building Dopetracks macOS app bundle.
"""

block_cipher = None

# Collect all data files
datas = [
    ('website', 'website'),  # Include frontend files
    ('packages', 'packages'),  # Include Python package
]

# Hidden imports - PyInstaller might miss these
hiddenimports = [
    # Uvicorn components
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.protocols.websockets.websockets_impl',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.http.httptools_impl',
    'uvicorn.loops.auto',
    'uvicorn.loops.asyncio',
    'uvicorn.logging',
    # FastAPI
    'fastapi',
    'fastapi.applications',
    'fastapi.routing',
    'fastapi.middleware',
    'fastapi.middleware.cors',
    'fastapi.staticfiles',
    'fastapi.responses',
    'fastapi.requests',
    # SQLAlchemy
    'sqlalchemy',
    'sqlalchemy.orm',
    'sqlalchemy.engine',
    'sqlalchemy.pool',
    # Database drivers
    'sqlite3',
    # Spotify
    'spotipy',
    'spotipy.oauth2',
    # Data processing
    'pandas',
    'numpy',
    'pytypedstream',
    # HTTP clients
    'httpx',
    'requests',
    # Other
    'dotenv',
    'python_dotenv',
    'bcrypt',
    'jose',
    'passlib',
    'tqdm',
    'multipart',
]

a = Analysis(
    ['launch_bundled.py'],  # Entry point
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',  # Not needed
        'pytest',  # Not needed in production
        'IPython',  # Not needed in production
        'jupyter',  # Not needed in production
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Dopetracks',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Compress executable
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No terminal window (set to True for debugging)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,  # Set to your Developer ID for code signing
    entitlements_file=None,  # Path to entitlements.plist for notarization
)

app = BUNDLE(
    exe,
    name='Dopetracks.app',
    icon=None,  # Set to 'resources/icon.icns' when you have an icon
    bundle_identifier='com.dopetracks.app',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': 'True',
        'NSRequiresAquaSystemAppearance': False,
        'LSMinimumSystemVersion': '10.15',  # macOS Catalina+
        'NSFullDiskAccessUsageDescription': 'Dopetracks needs Full Disk Access to read your Messages database and create Spotify playlists from shared songs.',
        'CFBundleName': 'Dopetracks',
        'CFBundleDisplayName': 'Dopetracks',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundlePackageType': 'APPL',
        'CFBundleExecutable': 'Dopetracks',
        'CFBundleIconFile': '',  # Set when you have an icon
    },
)

