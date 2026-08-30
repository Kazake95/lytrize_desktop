<#
  build_windows.ps1 -- Build the Lytrize Windows installer with Inno Setup 7.

  Sits in the repository root, mirroring build.sh / build_rpm.sh for Linux.

  What it does:
    1. Locates Python (3.11+) and Inno Setup 7 (ISCC.exe).
    2. Prepares a staging folder containing backend\ , desktop\ ,
       requirements.txt and a freshly created venv with all dependencies.
    3. Slims the venv: __pycache__/tests plus the PySide6 Qt modules the app
       never uses (WebEngine, QML/Quick, 3D, Charts, Designer, Graphs, ...).
       The launcher only needs QtCore/QtGui/QtWidgets, so this removes
       thousands of files -- a much smaller installer AND far less exposure
       to antivirus interference during ISCC compression. A smoke test
       verifies PySide6 still imports after slimming, so a broken install
       can never ship.
    4. Invokes ISCC.exe (with retries) to compile packaging\windows\lytrize.iss
       into packaging\windows\Output\LytrizeSetup_<ver>.exe.

  Usage (from the repository root):
    powershell -ExecutionPolicy Bypass -File build_windows.ps1
    powershell -ExecutionPolicy Bypass -File build_windows.ps1 -PythonExe C:\Python311\python.exe
    powershell -ExecutionPolicy Bypass -File build_windows.ps1 -UseTempStaging

  -UseTempStaging stages the venv on the local NTFS %TEMP% drive instead of
  the repo drive. Use it if ISCC reports "The volume for a file has been
  externally altered" (typical on removable/exFAT build drives or with
  aggressive real-time antivirus scanning).
#>
param(
    [string]$PythonExe = "",
    [string]$InnoSetupPath = "C:\Program Files\Inno Setup 7\ISCC.exe",
    [switch]$UseTempStaging
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root       = $PSScriptRoot                                # repository root
$WindowsDir = Join-Path $Root "packaging\windows"
$IssFile    = Join-Path $WindowsDir "lytrize.iss"

# Build artifacts live in a root-level build\ folder, mirroring build.sh /
# build_rpm.sh: the final installer drops into build\ next to the .deb.
$BuildDir  = Join-Path $Root "build"
$OutputDir = $BuildDir

if ($UseTempStaging) {
    # NTFS %TEMP% override for antivirus / exFAT build-volume problems.
    $Staging = Join-Path ([System.IO.Path]::GetTempPath()) "lytrize_build_staging"
} else {
    $Staging = Join-Path $BuildDir "windows-staging"
}

$AppName = "Lytrize"
$Version = "1.1"

Write-Host "================ Lytrize Windows installer builder ================"
Write-Host "Repo root  : $Root"
Write-Host "Staging    : $Staging"
Write-Host "ISCC       : $InnoSetupPath"
Write-Host ""

# ── 1. Locate Python ────────────────────────────────────────────────────────
if (-not $PythonExe) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $cmd) { $cmd = Get-Command py -ErrorAction SilentlyContinue }
    if ($cmd) { $PythonExe = $cmd.Source }
}
if (-not $PythonExe -or -not (Test-Path $PythonExe)) {
    Write-Error "Python 3.11+ was not found. Pass -PythonExe C:\path\to\python.exe"
}
Write-Host "[1/6] Using Python: $PythonExe"

# ── 2. Locate Inno Setup 7 ──────────────────────────────────────────────────
if (-not (Test-Path $InnoSetupPath)) {
    Write-Error "Inno Setup 7 ISCC.exe not found at: $InnoSetupPath"
}
Write-Host "[2/6] Using Inno Setup: $InnoSetupPath"

# ── 3. Prepare staging folder ───────────────────────────────────────────────
Write-Host "[3/6] Preparing staging folder: $Staging"
if (Test-Path $Staging) { Remove-Item -Recurse -Force $Staging }
New-Item -ItemType Directory -Force -Path $Staging | Out-Null

Copy-Item -Recurse -Force (Join-Path $Root "backend")  (Join-Path $Staging "backend")
Copy-Item -Recurse -Force (Join-Path $Root "desktop")  (Join-Path $Staging "desktop")
Copy-Item -Force (Join-Path $Root "requirements.txt")  (Join-Path $Staging "requirements.txt")

# Drop __pycache__ / stale bytecode from the copied sources.
Get-ChildItem -Path $Staging -Recurse -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path $Staging -Recurse -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -in ".pyc", ".pyo" } |
    Remove-Item -Force -ErrorAction SilentlyContinue

# ── 4. Create the venv and install runtime dependencies ─────────────────────
Write-Host "[4/6] Creating venv and installing dependencies (this can take a while)..."
$VenvDir = Join-Path $Staging "venv"
& $PythonExe -m venv $VenvDir
if ($LASTEXITCODE -ne 0) { throw "Failed to create virtual environment with $PythonExe" }

$Pip = Join-Path $VenvDir "Scripts\pip.exe"
if (-not (Test-Path $Pip)) { $Pip = Join-Path $VenvDir "Scripts\pip3.exe" }

& $Pip install --upgrade pip setuptools wheel | Out-Host
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }

& $Pip install -r (Join-Path $Root "requirements.txt") | Out-Host
if ($LASTEXITCODE -ne 0) { throw "pip install -r requirements.txt failed" }

# ── 5. Slim the venv ────────────────────────────────────────────────────────
Write-Host "[5/6] Slimming installed venv..."
Get-ChildItem -Path $VenvDir -Recurse -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path $VenvDir -Recurse -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -in "tests", "test", "docs" } |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# ── 5b. Slim unused PySide6 Qt modules ──────────────────────────────────────
# The launcher only uses QtCore / QtGui / QtWidgets. Everything below is
# dead weight for this app (WebEngine alone is hundreds of MB) and each
# removed file also reduces ISCC's exposure to antivirus / volume errors.
$PySide6Dir = Join-Path $VenvDir "Lib\site-packages\PySide6"
if (Test-Path $PySide6Dir) {
    $SizeBefore = (Get-ChildItem -Path $PySide6Dir -Recurse -File -ErrorAction SilentlyContinue |
                   Measure-Object -Property Length -Sum).Sum

    # Qt C++ DLLs shipped inside the PySide6 wheel (Qt6*.dll).
    $unusedQtDllPatterns = @(
        "Qt6WebEngine*.dll",  "Qt6Pdf*.dll",          "Qt6Qml*.dll",
        "Qt6Quick*.dll",      "Qt6Quick3D*.dll",      "Qt63D*.dll",
        "Qt6Charts*.dll",     "Qt6DataVisualization*.dll",
        "Qt6Designer*.dll",   "Qt6Graphs*.dll",       "Qt6Multimedia*.dll",
        "Qt6Sensors*.dll",    "Qt6SerialPort*.dll",   "Qt6Positioning*.dll",
        "Qt6Location*.dll",   "Qt6RemoteObjects*.dll","Qt6Scxml*.dll",
        "Qt6WebChannel*.dll", "Qt6WebSockets*.dll",   "Qt6NetworkAuth*.dll",
        "Qt6HttpServer*.dll", "Qt6TextToSpeech*.dll", "Qt6VirtualKeyboard*.dll",
        "Qt6Help*.dll",       "Qt6UiTools*.dll",      "Qt6Test*.dll",
        "Qt6Bluetooth*.dll",  "Qt6Nfc*.dll",          "Qt6Labs*.dll",
        "Qt6SpatialAudio*.dll", "Qt6WebView*.dll"
    )
    # PySide6 Python extension modules matching the removed Qt libraries.
    $unusedQtPydPatterns = @(
        "QtWebEngine*.pyd",   "QtPdf*.pyd",           "QtQml*.pyd",
        "QtQuick*.pyd",       "QtCharts*.pyd",        "QtDataVisualization*.pyd",
        "Qt3D*.pyd",          "QtPositioning*.pyd",   "QtLocation*.pyd",
        "QtSensors*.pyd",     "QtSerialPort*.pyd",    "QtScxml*.pyd",
        "QtRemoteObjects*.pyd","QtWebChannel*.pyd",   "QtWebSockets*.pyd",
        "QtNetworkAuth*.pyd", "QtHttpServer*.pyd",    "QtTextToSpeech*.pyd",
        "QtDesigner*.pyd",    "QtUiTools*.pyd",       "QtTest*.pyd",
        "QtBluetooth*.pyd",   "QtNfc*.pyd",           "QtGraphs*.pyd",
        "QtMultimedia*.pyd",  "QtHelp*.pyd",          "QtSpatialAudio*.pyd",
        "QtWebView*.pyd",     "QtQuick3D*.pyd"
    )

    foreach ($pattern in ($unusedQtDllPatterns + $unusedQtPydPatterns)) {
        Get-ChildItem -Path $PySide6Dir -Recurse -File -Filter $pattern -ErrorAction SilentlyContinue |
            Remove-Item -Force -ErrorAction SilentlyContinue
    }

    # NOTE (PySide6 >= 6.10 wheel layout): plugins/qml/resources/translations
    # live directly under PySide6\ (there is no Qt\ subdirectory), DLLs sit in
    # the PySide6 root, and typesystems\ is REQUIRED at runtime -- keep it.
    $unusedPluginDirs = @(
        "plugins\webview",     "plugins\multimedia",  "plugins\position",
        "plugins\sensors",     "plugins\sceneparsers","plugins\geometryloaders",
        "plugins\canbus",      "plugins\renderers",   "plugins\renderplugins",
        "plugins\geoservices", "plugins\scxmldatamodel",
        "plugins\texttospeech","plugins\qmltooling",  "plugins\qmllint",
        "plugins\designer",    "plugins\assetimporters"
    )
    foreach ($rel in $unusedPluginDirs) {
        Remove-Item -Recurse -Force (Join-Path $PySide6Dir $rel) -ErrorAction SilentlyContinue
    }
    Remove-Item -Force (Join-Path $PySide6Dir "plugins\imageformats\qpdf.dll") -ErrorAction SilentlyContinue

    # QML module tree, WebEngine resources, and C++ dev-only trees are pure
    # dead weight for a runtime install.
    Remove-Item -Recurse -Force (Join-Path $PySide6Dir "qml") -ErrorAction SilentlyContinue
    foreach ($devDir in @("doc", "glue", "include", "lib", "metatypes", "scripts")) {
        Remove-Item -Recurse -Force (Join-Path $PySide6Dir $devDir) -ErrorAction SilentlyContinue
    }
    Get-ChildItem -Path (Join-Path $PySide6Dir "resources") -Filter "qtwebengine*" -ErrorAction SilentlyContinue |
        Remove-Item -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path (Join-Path $PySide6Dir "translations") -Filter "qtwebengine*" -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

    $SizeAfter = (Get-ChildItem -Path $PySide6Dir -Recurse -File -ErrorAction SilentlyContinue |
                  Measure-Object -Property Length -Sum).Sum
    Write-Host ("      PySide6 slimmed: {0:N0} MB -> {1:N0} MB" -f ($SizeBefore / 1MB), ($SizeAfter / 1MB))

    # Safety net: PySide6 must still import after slimming, or abort the build
    # so a broken installer can never be produced.
    & (Join-Path $VenvDir "Scripts\python.exe") -c "from PySide6 import QtCore, QtGui, QtWidgets; print('PySide6 smoke test OK, Qt', QtCore.qVersion())"
    if ($LASTEXITCODE -ne 0) {
        throw "PySide6 smoke test FAILED after Qt slimming -- refusing to build an installer."
    }
} else {
    Write-Host "      PySide6 not found in venv -- skipping Qt slimming."
}

# ── 6. Compile the installer (with retries) ─────────────────────────────────
# ISCC compresses thousands of venv files; real-time antivirus scanning a DLL
# mid-read can abort a run with "The volume for a file has been externally
# altered". Retrying after a short pause almost always succeeds.
$IsccArgs = @("/DAppVersion=$Version", "/DStaging=$Staging", "/DOutputDir=$OutputDir", "/DAppRoot=$Root", $IssFile)
$MaxAttempts = 3
$Compiled = $false

for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
    Write-Host "[6/6] Compiling installer with ISCC (attempt $attempt of $MaxAttempts)..."
    Remove-Item -Recurse -Force $OutputDir -ErrorAction SilentlyContinue

    & $InnoSetupPath @IsccArgs
    if ($LASTEXITCODE -eq 0) { $Compiled = $true; break }

    if ($attempt -lt $MaxAttempts) {
        Write-Warning "ISCC failed (exit $LASTEXITCODE). Retrying in 5 seconds..."
        Start-Sleep -Seconds 5
    }
}

if (-not $Compiled) {
    Write-Host ""
    Write-Host "ISCC kept failing. This is almost always antivirus real-time scanning" -ForegroundColor Yellow
    Write-Host "or a non-NTFS (exFAT/removable) build volume. Try one of:" -ForegroundColor Yellow
    Write-Host "  1. Exclude the staging folder from your antivirus, e.g. (admin):" -ForegroundColor Yellow
    Write-Host "       Add-MpPreference -ExclusionPath `\"$Staging`\"" -ForegroundColor Yellow
    Write-Host "  2. Re-run with -UseTempStaging to stage the venv on the local NTFS drive:" -ForegroundColor Yellow
    Write-Host "       powershell -ExecutionPolicy Bypass -File build_windows.ps1 -UseTempStaging" -ForegroundColor Yellow
    throw "ISCC compile failed after $MaxAttempts attempts"
}


$Setup = Join-Path $OutputDir "${AppName}Setup_${Version}.exe"
Write-Host ""
Write-Host "================ BUILD COMPLETE ================"
Write-Host "Installer : $Setup"
if (Test-Path $Setup) {
    $size = (Get-Item $Setup).Length / 1MB
    Write-Host ("Size      : {0:N1} MB" -f $size)
}
Write-Host "Install   : double-click the exe (admin prompt will appear)"
Write-Host "================================================="