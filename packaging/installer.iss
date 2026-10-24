; StoryForge 安装包脚本（Inno Setup 6）
;
; **本仓库不自动跑它** —— 装 Inno Setup 属于改系统，由作者决定。
; 步骤：
;   1. 装 Inno Setup 6：https://jrsoftware.org/isdl.php
;   2. 先跑一次 scripts/build.ps1，确认 backend/dist/StoryForge/StoryForge.exe 存在
;   3. 在仓库根执行：
;        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss
;   4. 产物：packaging/Output/StoryForge-Setup-<版本>.exe
;
; 要点：**安装包只装程序本体**。数据目录 %LOCALAPPDATA%\StoryForge\ 由程序首次运行
; 时自己创建，卸载时保留 —— 卸载应用不该删掉作者的书稿。

#define AppName "StoryForge"
#define AppVersion "0.1.0"
#define AppPublisher "StoryForge"
#define AppExe "StoryForge.exe"

[Setup]
AppId={{8E2B7C41-5A3D-4F16-9C7A-1D2E3F4A5B6C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; 一期只支持 64 位 Windows 10/11。
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; 需要 WebView2 运行时；Win10/11 通常自带，缺失时安装器会提示去装。
; （不内嵌 Evergreen 引导器：它会联网下载，与「本机优先」不符。）

; 语言：Inno 6.7 官方安装包**不带**简体中文 .isl（它在 jrsoftware/issrc 的
; `Files/Languages/Unofficial/` 里，需要单独放进来）。本机没有外网、取不到，
; 因此默认走英文向导。要中文向导：把 `ChineseSimplified.isl` 放到
; `%LOCALAPPDATA%\Programs\Inno Setup 6\Languages\` 或本目录 `languages\` 下，
; 再把下面这行的注释去掉。
;
; [Languages]
; Name: "chinesesimplified"; MessagesFile: "languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："; Flags: unchecked

[Files]
; onedir 产物的全部内容。
Source: "..\backend\dist\StoryForge\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "启动 {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 只清程序目录里的东西。数据目录（%LOCALAPPDATA%\StoryForge\）**不动**。
Type: filesandordirs; Name: "{app}"
