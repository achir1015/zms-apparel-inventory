; 資料助秘工具之服飾業進銷存系統 — Windows 安裝程式（Inno Setup 6）
; 建置：python tools\build_windows.py（會先打包程式再呼叫 ISCC）
#ifndef AppVer
  #define AppVer "0.5.0"
#endif
#define AppName "資料助秘工具之服飾業進銷存系統"
#define AppExe "ZMSInventory.exe"

[Setup]
AppId={{6C2F7A51-3E8B-4D6A-9B1C-5A7E2D90F431}
AppName={#AppName}
AppVersion={#AppVer}
AppVerName={#AppName} {#AppVer}
AppPublisher=吳玉柱
AppCopyright=系統開發：吳玉柱 先生 與 Claude AI Opus 5.5
DefaultDirName={autopf}\ZMSInventory
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline dialog
OutputDir=..\dist-installer
OutputBaseFilename=ZMSInventory-Setup-{#AppVer}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
CloseApplications=force
RestartApplications=no

[Languages]
Name: "cht"; MessagesFile: "ChineseTraditional.isl"

[Tasks]
Name: "desktopicon"; Description: "建立桌面捷徑"; GroupDescription: "其他："

[Files]
Source: "..\dist\ZMSInventory\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "mariadb\*"; DestDir: "{app}\mariadb"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\資料與紀錄資料夾"; Filename: "{localappdata}\ZMSInventory"
Name: "{group}\解除安裝 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[InstallDelete]
; v0.1.0 舊名稱的捷徑（改名為服飾業版後移除）
Type: files; Name: "{autodesktop}\資料助秘工具之進銷存系統.lnk"
Type: filesandordirs; Name: "{autoprograms}\資料助秘工具之進銷存系統"

[Dirs]
Name: "{localappdata}\ZMSInventory"

[Run]
Filename: "{app}\{#AppExe}"; Description: "立即開啟 {#AppName}"; Flags: nowait postinstall skipifsilent

[Messages]
cht.FinishedLabel=安裝完成。%n%n資料庫與設定存放在：%n%LOCALAPPDATA%\ZMSInventory%n（解除安裝不會刪除資料，請記得定期備份）

[Code]
// 解除安裝時保留資料：只提示位置
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    if not UninstallSilent then
      MsgBox('程式已移除。您的資料仍保留在：' + #13#10 + ExpandConstant('{localappdata}\ZMSInventory') + #13#10 + '如確定不再需要，可自行刪除該資料夾。', mbInformation, MB_OK);
end;
