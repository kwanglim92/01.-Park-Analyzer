$ErrorActionPreference = 'Continue'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

$ROOT = "C:\Users\Spare\Desktop\03. Program"
$PA = "$ROOT\01. Park Analyzer"
$MODULES = "$PA\modules"

Write-Host ""
Write-Host "============================================="
Write-Host "  Park Analyzer - Master Build Pipeline"
Write-Host "  (PyInstaller --onefile for Tools)"
Write-Host "  (PyInstaller --onedir  for Launcher)"
Write-Host "============================================="
Write-Host ""

# [1/6] Sample Surface Mapping
Write-Host "[1/6] Building: Sample Surface Mapping..."
$proj = "$ROOT\96. Sample_Surface_Mapping"
Set-Location $proj
python -m PyInstaller --noconfirm --onefile --windowed --name "SampleSurfaceMapping" --distpath dist --add-data "$proj\config;config" --hidden-import=analyzers --hidden-import=controllers --hidden-import=core --hidden-import=parsers --hidden-import=ui --hidden-import=utils main.py
if ($LASTEXITCODE -ne 0) { Write-Host "[FAIL] Sample Surface Mapping"; exit 1 }
Write-Host "[OK] Sample Surface Mapping"
Write-Host ""

# [2/6] XY Stage Offset
Write-Host "[2/6] Building: XY Stage Offset Analysis..."
$proj = "$ROOT\97. XY Stage Positioning Offset Analysis"
Set-Location $proj
python -m PyInstaller --noconfirm --onefile --windowed --name "XYStageOffset" --distpath dist --add-data "$proj\src\assets;src\assets" --hidden-import=src.core --hidden-import=src.ui --hidden-import=src.charts src\main.py
if ($LASTEXITCODE -ne 0) { Write-Host "[FAIL] XY Stage Offset"; exit 1 }
Write-Host "[OK] XY Stage Offset Analysis"
Write-Host ""

# [3/6] Sliding Stage OPM
Write-Host "[3/6] Building: Sliding Stage OPM..."
$proj = "$ROOT\80. Sliding Stage OPM Repeatability"
Set-Location $proj
python -m PyInstaller --noconfirm --onefile --windowed --name "SlidingStageOPM" --distpath dist --hidden-import=src.core --hidden-import=src.ui --hidden-import=src.visualization main.py
if ($LASTEXITCODE -ne 0) { Write-Host "[FAIL] Sliding Stage OPM"; exit 1 }
Write-Host "[OK] Sliding Stage OPM"
Write-Host ""

# [4/6] Copy .exe to modules/
Write-Host "[4/6] Copying Tool .exe to modules/..."
Copy-Item -Force "$ROOT\96. Sample_Surface_Mapping\dist\SampleSurfaceMapping.exe" "$MODULES\sample_surface_mapping\main.exe"
Write-Host "  - sample_surface_mapping\main.exe"
Copy-Item -Force "$ROOT\97. XY Stage Positioning Offset Analysis\dist\XYStageOffset.exe" "$MODULES\xy_stage_offset\main.exe"
Write-Host "  - xy_stage_offset\main.exe"
Copy-Item -Force "$ROOT\80. Sliding Stage OPM Repeatability\dist\SlidingStageOPM.exe" "$MODULES\sliding_stage_opm\main.exe"
Write-Host "  - sliding_stage_opm\main.exe"
if (Test-Path "$ROOT\03. VMoption\VMOptionGenerator.exe") {
    Copy-Item -Force "$ROOT\03. VMoption\VMOptionGenerator.exe" "$MODULES\vmoption\VMOptionGenerator.exe"
    Write-Host "  - vmoption\VMOptionGenerator.exe"
}
Write-Host "[OK] All Tool .exe copied!"
Write-Host ""

# [5/6] Launcher
Write-Host "[5/6] Building: Park Analyzer Launcher..."
Set-Location $PA
python -m PyInstaller --noconfirm --onedir --windowed --name "ParkAnalyzer" --icon "$PA\assets\app.ico" --distpath dist --add-data "$PA\config;config" --add-data "$PA\assets;assets" --hidden-import=core --hidden-import=ui main.py
if ($LASTEXITCODE -ne 0) { Write-Host "[FAIL] Park Analyzer"; exit 1 }

Write-Host "Copying modules to dist..."
if (Test-Path "dist\ParkAnalyzer\modules") { Remove-Item -Recurse -Force "dist\ParkAnalyzer\modules" }
Copy-Item -Recurse -Force "modules" "dist\ParkAnalyzer\modules"
Write-Host "[OK] Park Analyzer + modules bundled!"
Write-Host ""

# [6/6] Code Signing
Write-Host "[6/6] Code Signing..."
$signScript = "$PA\installer\_sign_all.ps1"
if (Test-Path $signScript) {
    & $signScript
} else {
    Write-Host "[SKIP] sign script not found."
}

Write-Host ""
Write-Host "============================================="
Write-Host "  BUILD COMPLETE!"
Write-Host "============================================="
Write-Host ""
Write-Host "  Launcher: dist\ParkAnalyzer\ParkAnalyzer.exe"
Write-Host ""
Write-Host "  Next: build.bat inno  (to create installer)"
Write-Host ""
