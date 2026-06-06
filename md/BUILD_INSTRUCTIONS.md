# Building XIV Downscale Utility as a Single Executable

## Prerequisites

1. Python 3.9 or higher installed
2. All dependencies installed (run `pip install -r requirements.txt`)

## Build Instructions

### Method 1: Using the Build Script (Recommended)

1. Open Command Prompt or PowerShell in the project directory
2. Run the build script:
   ```batch
   build_exe.bat
   ```
3. Wait for the build to complete
4. Find the executable in the `dist` folder: `dist\XIV_Downscale_Utility.exe`

### Method 2: Manual PyInstaller Command

If you prefer to run PyInstaller manually:

```bash
# Install PyInstaller
pip install pyinstaller

# Run PyInstaller
pyinstaller --name="XIV_Downscale_Utility" --onefile --windowed --icon="icon.ico" --add-data="icon.ico;." --add-data="DirectXTex/bin/x64/release/DirectXTex.dll;DirectXTex/bin/x64/release" --add-data="id_ranges.txt;." --add-data="id_edgecases.txt;." --hidden-import="PySide6.QtCore" --hidden-import="PySide6.QtGui" --hidden-import="PySide6.QtWidgets" --hidden-import="texture2ddecoder" --hidden-import="kaitaistruct" --collect-all="texture2ddecoder" main.py
```

## Build Output

- **dist/XIV_Downscale_Utility.exe** - The main executable (single file, portable)
- **build/** - Temporary build files (can be deleted)
- **XIV_Downscale_Utility.spec** - PyInstaller specification file (can be deleted)

## Distribution

The `dist/XIV_Downscale_Utility.exe` file is completely standalone and portable. You can:
- Copy it to any Windows PC
- Run it without installing Python or any dependencies
- Share it with others

## Troubleshooting

### Build fails with "Module not found" error
- Make sure all dependencies are installed: `pip install -r requirements.txt`
- Make sure you're running from the correct directory

### Executable doesn't start or crashes
- Run the executable from Command Prompt to see error messages
- Check that all data files (icon.ico, DirectXTex.dll, etc.) are being bundled correctly

### Antivirus flags the executable
- This is a false positive common with PyInstaller executables
- You may need to add an exception in your antivirus software
- Alternatively, use `--onedir` instead of `--onefile` in the build script

## Notes

- The build process may take several minutes
- The resulting .exe file will be around 100-200 MB (includes Python runtime and all dependencies)
- First launch may be slower as Windows scans the new executable
