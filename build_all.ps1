$ErrorActionPreference = 'Continue'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

$PA = $PSScriptRoot
$MODULES = "$PA\modules"

# Read names from settings.json
$settingsPath = Join-Path $PA "config\settings.json"
$settings = Get-Content $settingsPath -Encoding UTF8 | ConvertFrom-Json
$BuildName = $settings.app.build_name
$DisplayName = $settings.app.display_name
$ExeName = $DisplayName -replace ' ', ''

Write-Host ""
Write-Host "============================================="
Write-Host "  $DisplayName - Master Build Pipeline"
Write-Host "============================================="
Write-Host ""

# ─────────────────────────────────────────
#  [1/4] Build Module Tools (from module.json)
# ─────────────────────────────────────────
Write-Host "[1/4] Building Module Tools..."
Write-Host ""

$moduleJsons = Get-ChildItem "$MODULES\*\module.json" -ErrorAction SilentlyContinue
$toolCount = 0
$toolTotal = ($moduleJsons | Measure-Object).Count

foreach ($jsonFile in $moduleJsons) {
    $mod = Get-Content $jsonFile.FullName -Encoding UTF8 | ConvertFrom-Json
    $build = $mod.build
    $modId = $mod.id
    $modName = $mod.name
    $devPath = $mod.dev_path

    if (-not $build) {
        Write-Host "  [$modName] SKIP (no build config)"
        continue
    }

    $toolCount++
    $method = $build.method

    switch ($method) {
        "pyinstaller" {
            Write-Host "  [$toolCount/$toolTotal] Building: $modName (PyInstaller)..."

            if (-not (Test-Path $devPath)) {
                Write-Host "  [WARN] dev_path not found: $devPath"
                continue
            }

            Set-Location $devPath

            # Build PyInstaller arguments
            $piArgs = @("--noconfirm")

            if ($build.onefile -eq $true) { $piArgs += "--onefile" } else { $piArgs += "--onedir" }
            if ($build.windowed -eq $true) { $piArgs += "--windowed" }

            $piArgs += "--name"
            $piArgs += $build.build_name
            $piArgs += "--distpath"
            $piArgs += "dist"

            # Hidden imports
            if ($build.hidden_imports) {
                foreach ($hi in $build.hidden_imports) {
                    $piArgs += "--hidden-import=$hi"
                }
            }

            # Add data
            if ($build.add_data) {
                foreach ($ad in $build.add_data) {
                    $fullSrc = $ad -replace '^([^;]+)', "$devPath\`$1"
                    $piArgs += "--add-data"
                    $piArgs += $fullSrc
                }
            }

            # Entry point
            $piArgs += $build.entry

            python -m PyInstaller @piArgs
            if ($LASTEXITCODE -ne 0) { Write-Host "  [FAIL] $modName"; exit 1 }

            # Copy built exe to modules/
            $builtExe = "$devPath\dist\$($build.build_name).exe"
            if (Test-Path $builtExe) {
                Copy-Item -Force $builtExe "$MODULES\$modId\$($mod.entry_prod)"
                Write-Host "  [OK] $modName -> modules\$modId\$($mod.entry_prod)"
            } else {
                Write-Host "  [WARN] Built exe not found: $builtExe"
            }
        }
        "copy" {
            Write-Host "  [$toolCount/$toolTotal] Copying: $modName..."

            $copyFrom = $build.copy_from
            $srcFile = Join-Path $devPath $copyFrom

            if (Test-Path $srcFile) {
                Copy-Item -Force $srcFile "$MODULES\$modId\$($mod.entry_prod)"
                Write-Host "  [OK] $modName -> modules\$modId\$($mod.entry_prod)"
            } else {
                Write-Host "  [WARN] Source not found: $srcFile"
            }
        }
        "none" {
            Write-Host "  [$toolCount/$toolTotal] $modName (skip - manual)"
        }
        default {
            Write-Host "  [$toolCount/$toolTotal] $modName (unknown method: $method)"
        }
    }
}

Write-Host ""
Write-Host "[OK] All module tools processed!"
Write-Host ""

# ─────────────────────────────────────────
#  [2/4] Build Launcher
# ─────────────────────────────────────────
Write-Host "[2/4] Building: $DisplayName Launcher..."
Set-Location $PA
python -m PyInstaller --noconfirm --onedir --windowed --name $BuildName --icon "$PA\assets\app.ico" --distpath dist --add-data "$PA\config;config" --add-data "$PA\assets;assets" --hidden-import=core --hidden-import=ui main.py
if ($LASTEXITCODE -ne 0) { Write-Host "[FAIL] $DisplayName"; exit 1 }

Write-Host "Copying modules to dist..."
if (Test-Path "dist\$BuildName\modules") { Remove-Item -Recurse -Force "dist\$BuildName\modules" }
Copy-Item -Recurse -Force "modules" "dist\$BuildName\modules"

# Rename to display name
Write-Host "Renaming to display name..."
$distBuild = "dist\$BuildName"
$distTarget = "dist\$ExeName"
if (Test-Path $distTarget) { Remove-Item -Recurse -Force $distTarget }
Rename-Item "$distBuild\$BuildName.exe" "$ExeName.exe"
Rename-Item $distBuild $ExeName
Write-Host "[OK] $DisplayName + modules bundled!"
Write-Host ""

# ─────────────────────────────────────────
#  [3/4] Code Signing
# ─────────────────────────────────────────
Write-Host "[3/4] Code Signing..."
$signScript = "$PA\installer\_sign_all.ps1"
if (Test-Path $signScript) {
    & $signScript
} else {
    Write-Host "[SKIP] sign script not found."
}
Write-Host ""

# ─────────────────────────────────────────
#  [4/4] Done
# ─────────────────────────────────────────
Write-Host "============================================="
Write-Host "  BUILD COMPLETE!"
Write-Host "============================================="
Write-Host ""
Write-Host "  Launcher: dist\$ExeName\$ExeName.exe"
Write-Host ""
Write-Host "  Next: build.bat inno  (to create installer)"
Write-Host ""
