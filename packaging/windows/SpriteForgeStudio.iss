#define AppName "SpriteForge Studio"
#ifndef AppVersion
  #define AppVersion "1.2.0"
#endif
#define AppPublisher "SpriteForge"
#define AppExeName "SpriteForgeStudio.exe"
#ifndef SourceRoot
  #define SourceRoot "..\.."
#endif

[Setup]
AppId={{F4EE898E-551D-4A7A-AB4F-77AB99E38B12}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\SpriteForge Studio
DefaultGroupName=SpriteForge Studio
OutputBaseFilename=SpriteForgeStudio-{#AppVersion}-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\app\web\favicon.ico
SetupLogging=yes

[Files]
Source: "{#SourceRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\SpriteForge Studio"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\SpriteForge Studio"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch SpriteForge Studio"; Flags: postinstall nowait skipifsilent
