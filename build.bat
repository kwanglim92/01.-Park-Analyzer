@echo off
chcp 65001 >nul 2>&1
REM ====================================================
REM  Park Analyzer - Build and Package Script
REM
REM  Usage:
REM    build.bat          Full build (PyInstaller + Sign + Inno Setup)
REM    build.bat build    PyInstaller build only
REM    build.bat sign     Sign only (after exe built)
REM    build.bat inno     Inno Setup only (after exe built)
REM ====================================================

set PROJECT_DIR=%~dp0
set DIST_DIR=%PROJECT_DIR%dist\ParkAnalyzer
set INNO_COMPILER="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
set SIGN_SCRIPT=%PROJECT_DIR%installer\sign.bat

REM --- FIX: Prevent mbcs UnicodeDecodeError ---
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo.
echo ============================================
echo   Park Analyzer - Build Pipeline
echo ============================================
echo.

REM --- Argument handling ---
if "%1"=="inno" goto :inno_setup
if "%1"=="sign" goto :code_sign
if "%1"=="build" goto :pyinstaller_build

:pyinstaller_build
echo [1/3] PyInstaller Build Starting...
echo   - Console window disabled
echo   - Output: %DIST_DIR%
echo.

python -m PyInstaller ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --name "ParkAnalyzer" ^
    --distpath dist ^
    --workpath build ^
    --specpath build ^
    --add-data "config;config" ^
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
echo   exe: %DIST_DIR%\ParkAnalyzer.exe
echo.

REM --- Copy modules/ to dist ---
echo Copying modules to dist...
if exist "%DIST_DIR%\modules" rmdir /s /q "%DIST_DIR%\modules"
xcopy /E /I /Y "%PROJECT_DIR%modules" "%DIST_DIR%\modules" >nul

echo Modules copied to dist\ParkAnalyzer\modules\
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

REM --- Check Inno Setup installation ---
if not exist %INNO_COMPILER% (
    if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
        set INNO_COMPILER="C:\Program Files\Inno Setup 6\ISCC.exe"
    ) else (
        echo.
        echo [WARNING] Inno Setup 6 NOT FOUND.
        echo   Download: https://jrsoftware.org/isdl.php
        echo.
        echo   Build was successful. Run exe directly:
        echo     %DIST_DIR%\ParkAnalyzer.exe
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

REM --- Sign the installer too ---
if exist "%SIGN_SCRIPT%" (
    if exist "installer\Output\Park_Analyzer_Setup.exe" (
        echo Signing installer...
        call "%SIGN_SCRIPT%" "installer\Output\Park_Analyzer_Setup.exe"
        echo.
    )
)

:done
echo.
echo ============================================
echo   Build Complete!
echo ============================================
echo.
echo   EXE:   dist\ParkAnalyzer\ParkAnalyzer.exe
echo   SETUP: installer\Output\Park_Analyzer_Setup.exe
echo.
pause
