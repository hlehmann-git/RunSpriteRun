; Inno Setup recipe: makes RunSpriteRun_Setup_v<version>.exe from the PyInstaller folder dist\RunSpriteRun.
; Built by the GitHub workflow: ISCC /DAppVersion=<version> packaging\RunSpriteRun.iss
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{4F253363-CD2F-4399-AD9E-C7B9D6793C5D}
AppName=RunSpriteRun
AppVersion={#AppVersion}
AppVerName=RunSpriteRun {#AppVersion}
AppPublisher=Harley Lehmann
; Per-user install: no administrator rights needed. The Browse button adds a RunSpriteRun sub-folder to the chosen place.
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\RunSpriteRun
AppendDefaultDirName=yes
DisableProgramGroupPage=yes
DefaultGroupName=RunSpriteRun
OutputDir=..\dist_installer
OutputBaseFilename=RunSpriteRun_Setup_v{#AppVersion}
UninstallDisplayIcon={app}\RunSpriteRun.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

[Tasks]
Name: "startmenuicon"; Description: "Create a Start Menu shortcut"; GroupDescription: "Shortcuts:"
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Dirs]
; The work folders live beside the program. The uninstaller never removes them.
Name: "{app}\Projects"; Flags: uninsneveruninstall
Name: "{app}\Exports"; Flags: uninsneveruninstall
Name: "{app}\Blank sprite sheets"; Flags: uninsneveruninstall

[Files]
Source: "..\dist\RunSpriteRun\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
; The example projects are put back only if they are missing, so a tester's changes to them are not overwritten.
Source: "..\Examples\*"; DestDir: "{app}\Examples"; Flags: recursesubdirs createallsubdirs onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{autoprograms}\RunSpriteRun"; Filename: "{app}\RunSpriteRun.exe"; Tasks: startmenuicon
Name: "{autoprograms}\RunSpriteRun files"; Filename: "{app}"; Tasks: startmenuicon
Name: "{autodesktop}\RunSpriteRun"; Filename: "{app}\RunSpriteRun.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\RunSpriteRun.exe"; Description: "Start RunSpriteRun"; Flags: nowait postinstall skipifsilent

[Code]
function StartsWith(const Text, Prefix: String): Boolean;
begin
  Result := (Prefix <> '') and (CompareText(Copy(Text, 1, Length(Prefix)), Prefix) = 0);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Dir: String;
begin
  Result := True;
  if CurPageID = wpSelectDir then
  begin
    Dir := WizardDirValue;
    if StartsWith(Dir, ExpandConstant('{commonpf}')) or StartsWith(Dir, ExpandConstant('{commonpf32}')) or
       StartsWith(Dir, ExpandConstant('{win}')) then
    begin
      MsgBox('Windows does not let RunSpriteRun save your work in this folder. Please choose another folder, ' +
             'for example one under your user folder.', mbInformation, MB_OK);
      Result := False;
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usDone then
    MsgBox('RunSpriteRun has been removed. Your Projects, Exports and Blank sprite sheets were left in:' + #13#10 +
           ExpandConstant('{app}'), mbInformation, MB_OK);
end;
