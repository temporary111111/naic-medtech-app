#ifndef AppVersion
  #define AppVersion "0.1.0-dev"
#endif
#ifndef Architecture
  #define Architecture "x64"
#endif
#ifndef SourceDir
  #error SourceDir must point to the packaged NDHI-LabRecords directory.
#endif
#ifndef OutputDir
  #error OutputDir must point to the installer output directory.
#endif

#define AppName "NDHI Laboratory Records"
#define AppPublisher "Naic Doctors Hospital, Incorporated"
#define AppExeName "NDHI-LabRecords.exe"
#define FirewallRuleName "NDHI Laboratory Records LAN"
#define AppPort "8114"
#define RuntimeDataDir "NDHI\LabRecords"
#define PrimaryDatabasePath "NDHI\LabRecords\database\ndhi_labrecords.db"
#define LegacyDatabasePath "NDHI\LabRecords\naic_medtech.db"

[Setup]
AppId={{4CB23F19-BA42-44ED-A0A9-A783A4B73590}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\NDHI\LabRecords
DefaultGroupName={#AppName}
OutputDir={#OutputDir}
OutputBaseFilename=NDHI-LabRecords-Setup-{#AppVersion}-{#Architecture}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#AppExeName}
#if Architecture == "x64"
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
#endif

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{commonappdata}\NDHI\LabRecords"; Flags: uninsneveruninstall
Name: "{commonappdata}\NDHI\LabRecords\database"; Flags: uninsneveruninstall
Name: "{commonappdata}\NDHI\LabRecords\uploads"; Flags: uninsneveruninstall
Name: "{commonappdata}\NDHI\LabRecords\backups"; Flags: uninsneveruninstall
Name: "{commonappdata}\NDHI\LabRecords\logs"; Flags: uninsneveruninstall
Name: "{commonappdata}\NDHI\LabRecords\config"; Flags: uninsneveruninstall

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
function RuntimeDatabaseExists(): Boolean;
begin
  Result :=
    FileExists(ExpandConstant('{commonappdata}\{#PrimaryDatabasePath}')) or
    FileExists(ExpandConstant('{commonappdata}\{#LegacyDatabasePath}'));
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ExistingExe: String;
  RuntimeDataPath: String;
  BackupParams: String;
  ResultCode: Integer;
begin
  Result := '';
  if not RuntimeDatabaseExists() then
  begin
    Log('Skipping pre-update backup because no runtime database exists.');
    Exit;
  end;

  ExistingExe := ExpandConstant('{app}\{#AppExeName}');
  RuntimeDataPath := ExpandConstant('{commonappdata}\{#RuntimeDataDir}');
  if not FileExists(ExistingExe) then
  begin
    Result :=
      'Existing NDHI Laboratory Records data was found, but Setup could not find the installed application executable needed to create a verified pre-update backup.' + #13#10 + #13#10 +
      'Expected executable:' + #13#10 + ExistingExe + #13#10 + #13#10 +
      'Setup stopped without changing the installed files. Create a manual backup or restore the existing installation before upgrading.';
    Exit;
  end;

  Log('Creating verified pre-update backup with existing installed executable: ' + ExistingExe);
  BackupParams := '--backup-now --data-dir "' + RuntimeDataPath + '" --reason pre-update';
  if not Exec(ExistingExe, BackupParams, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    Result :=
      'Setup could not start the verified pre-update backup.' + #13#10 + #13#10 +
      'Executable:' + #13#10 + ExistingExe + #13#10 + #13#10 +
      'Setup stopped without changing the installed files.';
    Exit;
  end;

  if ResultCode <> 0 then
  begin
    Result :=
      'The verified pre-update backup failed with exit code ' + IntToStr(ResultCode) + '.' + #13#10 + #13#10 +
      'Setup stopped without changing the installed files. Check the logs under:' + #13#10 +
      RuntimeDataPath + '\logs';
    Exit;
  end;

  Log('Verified pre-update backup completed successfully.');
end;

procedure ConfigureFirewallRule();
var
  ResultCode: Integer;
  AppPath: String;
begin
  AppPath := ExpandConstant('{app}\{#AppExeName}');
  Exec(
    ExpandConstant('{sys}\netsh.exe'),
    'advfirewall firewall delete rule name="{#FirewallRuleName}"',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  );
  Exec(
    ExpandConstant('{sys}\netsh.exe'),
    'advfirewall firewall add rule name="{#FirewallRuleName}" dir=in action=allow protocol=TCP localport={#AppPort} profile=private,domain remoteip=localsubnet program="' + AppPath + '" enable=yes',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  );
end;

procedure RemoveFirewallRule();
var
  ResultCode: Integer;
begin
  Exec(
    ExpandConstant('{sys}\netsh.exe'),
    'advfirewall firewall delete rule name="{#FirewallRuleName}"',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  );
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    ConfigureFirewallRule();
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    RemoveFirewallRule();
end;
