@echo off
REM ====================================================
REM  Integrated Analyzer - Build and Package Script
REM
REM  Usage:
REM    build.bat          Full build (PyInstaller + Sign + Inno Setup)
REM    build.bat build    PyInstaller build only
REM    build.bat sign     Sign only (after exe built)
REM    build.bat inno     Inno Setup only (after exe built)
REM
REM  NOTE: cmd.exe corrupts Korean chars in variable expansion.
REM        We build with ASCII name, then rename via PowerShell.
REM ====================================================

set PROJECT_DIR=%~dp0

REM --- Read build_name from settings.json (ASCII safe) ---
for /f "delims=" %%i in ('powershell -NoProfile -Command "(Get-Content '%~dp0config\settings.json' | ConvertFrom-Json).app.build_name"') do set BUILD_NAME=%%i
if not defined BUILD_NAME set BUILD_NAME=IntegratedAnalyzer

set DIST_DIR=%PROJECT_DIR%dist\%BUILD_NAME%
set INNO_COMPILER="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
set SIGN_SCRIPT=%PROJECT_DIR%installer\sign.bat
set RENAME_SCRIPT=%PROJECT_DIR%installer\_rename_dist.ps1

REM --- FIX: Prevent mbcs UnicodeDecodeError ---
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo.
echo ============================================
echo   Build Pipeline
echo ============================================
echo.

REM --- Clean old artifacts ---
if exist "%PROJECT_DIR%ParkAnalyzer.spec" del "%PROJECT_DIR%ParkAnalyzer.spec"
if exist "%PROJECT_DIR%dist\ParkAnalyzer" rmdir /s /q "%PROJECT_DIR%dist\ParkAnalyzer"
if exist "%PROJECT_DIR%build\ParkAnalyzer" rmdir /s /q "%PROJECT_DIR%build\ParkAnalyzer"

REM --- Argument handling ---
if "%1"=="inno" goto :inno_setup
if "%1"=="sign" goto :code_sign
if "%1"=="build" goto :pyinstaller_build

:pyinstaller_build
echo [1/3] PyInstaller Build Starting...
echo   - Console window disabled
echo   - Build name: %BUILD_NAME% (will be renamed to Korean)
echo.

REM --- Clean previous interim build if exists ---
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"

python -m PyInstaller ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --name "%BUILD_NAME%" ^
    --distpath dist ^
    --workpath build ^
    --specpath build ^
    --add-data "%PROJECT_DIR%config;config" ^
    --add-data "%PROJECT_DIR%assets;assets" ^
    --hidden-import=core ^
    --hidden-import=ui ^
    main.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] PyInstaller build failed!
    pause
    exit /b 1
)

echo.
echo [1/3] PyInstaller build SUCCESS!
echo.

REM --- Copy modules/ to dist ---
echo Copying modules to dist...
if exist "%DIST_DIR%\modules" rmdir /s /q "%DIST_DIR%\modules"
xcopy /E /I /Y "%PROJECT_DIR%modules" "%DIST_DIR%\modules" >nul

echo Modules copied.
echo.

REM --- Rename to Korean name (PowerShell handles UTF-8 natively) ---
echo [1/3] Renaming output to Korean name...
powershell -NoProfile -ExecutionPolicy Bypass -File "%RENAME_SCRIPT%" "%PROJECT_DIR%dist" "%BUILD_NAME%"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Rename to Korean name failed!
    pause
    exit /b 1
)

echo.

if "%1"=="build" goto :done

:code_sign
REM --- Code Signing ---
echo [2/3] Code Signing...
echo.

if exist "%SIGN_SCRIPT%" (
    call "%SIGN_SCRIPT%" --all
    if %ERRORLEVEL% neq 0 (
        echo.
        echo [WARNING] Code signing failed. Continuing without signing...
        echo   To fix: run installer\create_cert.ps1 first.
        echo.
    ) else (
        echo.
        echo [2/3] Code signing SUCCESS!
        echo.
    )
) else (
    echo [SKIP] sign.bat not found. Skipping code signing.
    echo.
)

if "%1"=="sign" goto :done

:inno_setup
echo [3/3] Inno Setup compile starting...

REM --- Generate setup.iss from template ---
echo Generating setup.iss from template...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_DIR%installer\_generate_iss.ps1"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to generate setup.iss!
    pause
    exit /b 1
)

REM --- Check Inno Setup installation ---
if not exist %INNO_COMPILER% (
    if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
        set INNO_COMPILER="C:\Program Files\Inno Setup 6\ISCC.exe"
    ) else (
        echo.
        echo [WARNING] Inno Setup 6 NOT FOUND.
        echo   Download: https://jrsoftware.org/isdl.php
        echo.
        pause
        exit /b 1
    )
)

%INNO_COMPILER% installer\setup.iss

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Inno Setup compile failed!
    pause
    exit /b 1
)

echo.
echo [3/3] Inno Setup compile SUCCESS!
echo.

REM --- Sign the installer too (delegate to PowerShell for Korean filename) ---
if exist "%SIGN_SCRIPT%" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_DIR%installer\_sign_installer.ps1" "%SIGN_SCRIPT%"
    echo.
)

:done
echo.
echo ============================================
echo   Build Complete!
echo ============================================
echo.
echo   Run: powershell -Command "Get-ChildItem dist -Directory; Get-ChildItem installer\Output\*.exe"
echo.
pause
