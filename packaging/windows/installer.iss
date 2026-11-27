; Windows-Installer (Inno Setup 6) für den QSL-Karten-Generator.
;
; Gebaut wird er im Release-Workflow aus dem fertigen PyInstaller-Ordner:
;
;   iscc /DAppVersion=0.4.0 /DSourceDir=dist\QSL-Karten-Generator ^
;        /DOutputDir=dist packaging\windows\installer.iss
;
; Bewusst **ohne Adminrechte** (PrivilegesRequired=lowest): installiert wird nach
; %LOCALAPPDATA%\Programs\QSL-Karten-Generator. Dort darf das Programm schreiben
; (Handbuch im Editor ergänzen, Portable-Modus), und es gibt keine UAC-Abfrage.
; Wer für alle Benutzer nach C:\Programme installieren will, wählt das im
; ersten Dialog („Für alle Benutzer installieren").
;
; Einstellungen, Cache und Protokoll liegen ohnehin in %APPDATA% und bleiben
; beim Deinstallieren erhalten.

#ifndef AppVersion
  #error "AppVersion fehlt: iscc /DAppVersion=X.Y.Z …"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\QSL-Karten-Generator"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif

#define AppName "QSL-Karten-Generator"
#define AppExe "QSL-Karten-Generator.exe"

[Setup]
; Die AppId nie ändern — an ihr erkennt Windows ein Update derselben Anwendung.
AppId={{A75BC0E1-F13B-4248-9098-FEF9F8C3BAFF}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=DA6IC
AppPublisherURL=https://github.com/da6ic/qsl-card-generator
AppSupportURL=https://github.com/da6ic/qsl-card-generator/issues
AppUpdatesURL=https://github.com/da6ic/qsl-card-generator/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
LicenseFile=..\..\LICENSE
SetupIconFile=..\..\qslcards\assets\icons\app_icon.ico
UninstallDisplayIcon={app}\{#AppExe}
OutputDir={#OutputDir}
OutputBaseFilename={#AppName}-{#AppVersion}-windows-x64-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Läuft das Programm noch, bietet Setup an, es zu schließen.
CloseApplications=yes

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; Ein Update ersetzt die Bibliotheken komplett — sonst blieben alte DLLs liegen.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
; LIESMICH.txt beschreibt das ZIP (entpacken, Ordner löschen) und passt hier nicht.
Source: "{#SourceDir}\*"; DestDir: "{app}"; Excludes: "LIESMICH.txt"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
