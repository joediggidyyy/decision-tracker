#ifndef BundleDir
  #error BundleDir is required
#endif
#ifndef ProductVersion
  #error ProductVersion is required
#endif
#ifndef OutputPath
  #error OutputPath is required
#endif

[Setup]
AppId={{48F6D0E0-478C-435E-9E76-8AF59BB81944}
AppName=Decision Tracker
AppVersion={#ProductVersion}
AppPublisher=Polymath Global
AppPublisherURL=https://github.com/joediggidyyy/decision-tracker
DefaultDirName={localappdata}\Programs\DecisionTracker
DefaultGroupName=Decision Tracker
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0.22000
OutputDir={#OutputPath}
OutputBaseFilename=DecisionTracker-{#ProductVersion}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=Decision Tracker {#ProductVersion}
UninstallDisplayIcon={app}\versions\{#ProductVersion}\runtime\site-packages\decision_tracker\static\favicon.ico
CloseApplications=no
RestartApplications=no
SetupLogging=yes
DisableProgramGroupPage=yes

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}\versions\{#ProductVersion}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Decision Tracker"; Filename: "{app}\versions\{#ProductVersion}\runtime\pythonw.exe"; Parameters: "-m decision_tracker.installed open --install-root ""{app}"""; WorkingDir: "{app}"; IconFilename: "{app}\versions\{#ProductVersion}\runtime\site-packages\decision_tracker\static\favicon.ico"
Name: "{autodesktop}\Decision Tracker"; Filename: "{app}\versions\{#ProductVersion}\runtime\pythonw.exe"; Parameters: "-m decision_tracker.installed open --install-root ""{app}"""; WorkingDir: "{app}"; IconFilename: "{app}\versions\{#ProductVersion}\runtime\site-packages\decision_tracker\static\favicon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\versions\{#ProductVersion}\runtime\pythonw.exe"; Parameters: "-m decision_tracker.installed open --install-root ""{app}"""; Description: "Launch Decision Tracker"; Flags: nowait postinstall skipifsilent

[Code]
function CurrentPython(): String;
var Text: AnsiString; Version: String;
begin
  Result := '';
  if LoadStringFromFile(ExpandConstant('{app}\current-version.txt'), Text) then begin
    Version := Trim(String(Text));
    if (Pos('\', Version) = 0) and (Pos('/', Version) = 0) and (Pos('..', Version) = 0) then
      Result := ExpandConstant('{app}\versions\') + Version + '\runtime\python.exe';
  end;
end;

function RunOwned(PythonPath, Action: String): Boolean;
var ExitCode: Integer; Arguments: String;
begin
  Arguments := '-m decision_tracker.installed ' + Action + ' --install-root "' + ExpandConstant('{app}') + '"';
  if Action = 'activate' then begin
    Arguments := Arguments + ' --deployment "' + ExpandConstant('{param:DEPLOYMENT|{localappdata}\DecisionTracker\deployment\deployment.json}') + '"';
    Arguments := Arguments + ' --port ' + ExpandConstant('{param:PORT|8765}');
  end;
  Result := Exec(PythonPath, Arguments, ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ExitCode) and (ExitCode = 0);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var PythonPath: String;
begin
  Result := '';
  PythonPath := CurrentPython();
  if (PythonPath <> '') and FileExists(PythonPath) then
    if not RunOwned(PythonPath, 'prepare') then
      Result := 'Decision Tracker could not stop safely. Close its unsaved drafts and retry. Your data is preserved. If files are damaged, use Repair instructions.';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var PythonPath, CliText: String;
begin
  if CurStep = ssPostInstall then begin
    PythonPath := ExpandConstant('{app}\versions\{#ProductVersion}\runtime\python.exe');
    if not RunOwned(PythonPath, 'activate') then
      RaiseException('Decision Tracker setup could not activate safely. Existing data is preserved. Run Setup again or follow the repair guide.');
    if not SaveStringToFile(ExpandConstant('{app}\current-version.txt'), '{#ProductVersion}', False) then
      RaiseException('Cannot save installation information. Run Setup again to repair it.');
    CliText := '@echo off' + #13#10 + '"%~dp0versions\{#ProductVersion}\runtime\python.exe" -m decision_tracker.cli %*' + #13#10;
    if not SaveStringToFile(ExpandConstant('{app}\decision-tracker.cmd'), CliText, False) then
      RaiseException('Cannot save the command launcher. Run Setup again to repair it.');
  end;
end;

function InitializeUninstall(): Boolean;
var PythonPath: String;
begin
  PythonPath := CurrentPython();
  Result := (PythonPath <> '') and FileExists(PythonPath) and RunOwned(PythonPath, 'uninstall');
  if not Result then
    SuppressibleMsgBox('Decision Tracker could not stop safely. Close unsaved drafts and retry. Your data is preserved. Reinstall missing application files before uninstalling.', mbError, MB_OK, IDOK);
end;

[UninstallDelete]
Type: files; Name: "{app}\decision-tracker.cmd"
Type: files; Name: "{app}\current-version.txt"
