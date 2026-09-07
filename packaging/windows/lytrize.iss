; =============================================================================
;  lytrize.iss -- Inno Setup 7 script for the Lytrize Windows installer.
;
;  Compile it via packaging/windows/build_lytrize_windows.ps1 (which prepares
;  the staging folder incl. the built venv and calls ISCC.exe).
;
;  Behaviour:
;    * Installs the app into the system directory  {autopf}\Lytrize
;      (require admin privileges).
;    * User data is written by the app itself to %APPDATA%\Lytrize and
;      %LOCALAPPDATA%\Lytrize.
;    * Uninstall removes EVERYTHING: the app folder AND all user data. It first
;      force-kills any running Lytrize launcher / backend processes to avoid
;      file locks. (Single-user-per-PC assumption.)
; =============================================================================
#ifndef AppVersion
  #define AppVersion "1.2"
#endif
#ifndef Staging
  #define Staging "packaging\windows\Staging"
#endif
#ifndef AppRoot
  #define AppRoot "..\.."
#endif
#ifndef OutputDir
  #define OutputDir "build"
#endif

#define AppName "Lytrize"
#define AppInternalName "lytrize"
#define AppPublisher "Lytrize"
#define AppURL "https://github.com/Kazake95/lytrize_desktop"
; Launcher: the venv's GUI python (no console window) + desktop/gui.py
#define LauncherExe "{app}\venv\Scripts\pythonw.exe"
#define LauncherArgs "desktop\gui.py"

[Setup]
AppId={{8D8D2A3B-7C01-4A9E-B0D5-3F1C94E62A13}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
; System directory install (admin required).
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
; 64-bit only (matches the amd64 Linux builds).
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputBaseFilename={#AppName}Setup_{#AppVersion}
OutputDir={#OutputDir}
SetupIconFile={#AppRoot}\backend\assets\lytrize.ico
UninstallDisplayIcon={app}\backend\assets\lytrize.ico
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#AppVersion}
; This installer is deliberately single-user-per-PC (see README): the user who
; elevates the install/uninstall is the same user whose %APPDATA% holds the
; Lytrize data, so the [UninstallDelete] entries below targeting
; {userappdata}/{localappdata} are correct. Silence Inno's per-user-area
; warning because that assumption is intentional, not accidental.
UsedUserAreasWarning=no
; Installer legal/info pages (MIT license + welcome + third-party notices).
; Each points to a plain-text file kept next to lytrize.iss.
LicenseFile=license.txt
InfoBeforeFile=info_before.txt
InfoAfterFile=third_party_notices.txt
; Friendly description in Add/Remove Programs and the final "Ready" dialog.
AppComments=Local-first, fully offline data analytics.

[CustomMessages]
LicenseText=Lytrize is free, open-source software (MIT License). Clicking "Next" accepts the license terms.
LicenseLabel=Lytrize license

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Application code (backend incl. assets, desktop launcher, requirements).
Source: "{#Staging}\backend\*";         DestDir: "{app}\backend";   Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Staging}\desktop\*";         DestDir: "{app}\desktop";   Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Staging}\requirements.txt";  DestDir: "{app}";           Flags: ignoreversion
; The isolated Python venv built by the PowerShell script.
Source: "{#Staging}\venv\*";            DestDir: "{app}\venv";      Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu + (optional) Desktop shortcuts straight to pythonw -> gui.py so no
; console window ever appears — only the launcher GUI and the isolated browser.
Name: "{autoprograms}\{#AppName}"; Filename: "{#LauncherExe}"; Parameters: "{#LauncherArgs}"; WorkingDir: "{app}"; IconFilename: "{app}\backend\assets\lytrize.ico"; Comment: "Launch {#AppName} Analytics"
Name: "{autodesktop}\{#AppName}";    Filename: "{#LauncherExe}"; Parameters: "{#LauncherArgs}"; WorkingDir: "{app}"; IconFilename: "{app}\backend\assets\lytrize.ico"; Comment: "Launch {#AppName} Analytics"; Tasks: desktopicon

[Registry]
; Allow "Run > Lytrize" and Add/Remove Programs niceties.
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\{#AppInternalName}.exe"; ValueType: string; ValueName: ""; ValueData: "{#LauncherExe}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\{#AppInternalName}.exe"; ValueType: string; ValueName: "Path"; ValueData: "{app}\venv\Scripts"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\{#AppPublisher}\{#AppName}"; ValueType: string; ValueName: "InstallLocation"; ValueData: "{app}"; Flags: uninsdeletekey

[Run]
Filename: "{#LauncherExe}"; Parameters: "{#LauncherArgs}"; WorkingDir: "{app}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

; -----------------------------------------------------------------------------
; Uninstall
; -----------------------------------------------------------------------------
[UninstallRun]
; Force-kill any running Lytrize launcher / backend (pythonw/python) before
; deleting files so no file is locked. The in-app "Stop & Quit" already closes
; the isolated browser windows too.
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM pythonw.exe"; Flags: runhidden; RunOnceId: "KillPythonW"
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM python.exe";      Flags: runhidden; RunOnceId: "KillPython"

[UninstallDelete]
; Remove ALL user data (single-user-per-PC assumption). The app stores its DB,
; launcher prefs, browser profiles and logs under %APPDATA% and parquet
; snapshots under %LOCALAPPDATA%.
Type: filesandordirs; Name: "{userappdata}\{#AppName}"
Type: filesandordirs; Name: "{localappdata}\{#AppName}"