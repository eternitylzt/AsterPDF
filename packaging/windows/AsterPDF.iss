; Optional Inno Setup 6 installer. Build the PyInstaller directory first.
[Setup]
AppId={{7DDA0BC4-4D07-4EEC-8D84-CBDCEBA6E3A9}
AppName=AsterPDF
AppVersion=1.2.1
DefaultDirName={localappdata}\Programs\AsterPDF
DefaultGroupName=AsterPDF
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=AsterPDF-1.2.1-windows-setup
SetupIconFile=..\..\assets\asterpdf.ico
LicenseFile=..\..\LICENSE
Compression=lzma2
SolidCompression=yes
[Files]
Source: "..\..\dist\AsterPDF\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs
[Icons]
Name: "{group}\AsterPDF"; Filename: "{app}\AsterPDF.exe"
Name: "{autodesktop}\AsterPDF"; Filename: "{app}\AsterPDF.exe"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"
[Run]
Filename: "{app}\AsterPDF.exe"; Description: "Launch AsterPDF"; Flags: nowait postinstall skipifsilent
