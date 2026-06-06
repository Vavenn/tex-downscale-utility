@echo off
echo ========================================
echo XIV Downscale Utility - Build Script
echo ========================================
echo.

REM Activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
) else (
    echo Warning: No .venv found. Using system Python.
)

REM Install PyInstaller if not installed
echo.
echo Installing/Updating PyInstaller...
pip install pyinstaller>=5.13.0

REM Clean previous builds
echo.
echo Cleaning previous builds...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist
if exist "XIV_Downscale_Utility.spec" del /q XIV_Downscale_Utility.spec

REM Build the executable
echo.
echo Building executable...
pyinstaller ^
    --name="XIV_Downscale_Utility" ^
    --onefile ^
    --windowed ^
    --icon="icon.ico" ^
    --add-data="icon.ico;." ^
    --add-data="splash.png;." ^
    --add-data="DirectXTex/bin/x64/release/DirectXTex.dll;DirectXTex/bin/x64/release" ^
    --add-data="id_ranges.txt;." ^
    --add-data="id_edgecases.txt;." ^
    --add-data="FFXIV Tex Converter/src;FFXIV Tex Converter/src" ^
    --hidden-import="PySide6.QtCore" ^
    --hidden-import="PySide6.QtGui" ^
    --hidden-import="PySide6.QtWidgets" ^
    --hidden-import="texture2ddecoder" ^
    --hidden-import="kaitaistruct" ^
    --collect-all="texture2ddecoder" ^
    main.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo BUILD SUCCESSFUL!
    echo ========================================
    echo Executable location: dist\XIV_Downscale_Utility.exe
    echo.
) else (
    echo.
    echo ========================================
    echo BUILD FAILED!
    echo ========================================
    echo Please check the error messages above.
    echo.
)

pause
