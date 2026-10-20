; 타임줍(TimeZoop) 설치 파일 — Inno Setup 6
; 만들기: packaging\build.ps1 (PyInstaller 빌드 → 개인정보 검사 → 이 스크립트 컴파일)
; 결과: build\installer\TimeZoop_Setup_<버전>.exe

#define AppName "타임줍"
#define AppNameEn "TimeZoop"
#define AppVersion "0.1.0"
#define AppExe "TimeZoop.exe"

[Setup]
AppId={{6E7C2B1A-3F5D-4C8E-9A21-7B0D5E3F9C42}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppName}
; 설치 폴더는 사용자가 고를 수 있다. 기본값: 나만 쓰기 → %LOCALAPPDATA%\Programs, 모든 사용자 → Program Files
DefaultDirName={autopf}\{#AppNameEn}
DisableDirPage=no
DefaultGroupName={#AppName}
; 기본은 관리자 권한 없이 설치. 시작할 때 "모든 사용자용(관리자)"도 고를 수 있다
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; 제거 때 지우는 설정·데이터 폴더는 설치한 사용자 것이라는 경고를 끈다 (의도한 동작)
UsedUserAreasWarning=no
OutputDir=..\build\installer
OutputBaseFilename={#AppNameEn}_Setup_{#AppVersion}
SetupIconFile=..\soop_timeline\web\app.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName} ({#AppNameEn})
; 최대 압축. 불필요한 CUDA 파일을 뺀 뒤에는 2GB 아래라 조각 파일(.bin) 없이 설치 exe 하나로 만든다
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
DiskSpanning=no
WizardStyle=modern
; 설치 창을 기본보다 크게, 가장자리를 끌어 크기 조절도 가능하게
WizardSizePercent=130,130
WizardResizable=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 아이콘 만들기"; GroupDescription: "추가 아이콘:"

[Files]
Source: "..\build\dist\TimeZoop\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; 바로가기 아이콘은 따로 둔 파일을 쓴다. 로고를 바꿀 때 이 파일 이름도 바꾸면 Windows에 남은 예전 아이콘 그림이 쓰이지 않는다.
Source: "..\soop_timeline\web\app.ico"; DestDir: "{app}"; DestName: "TimeZoop_tz.ico"; Flags: ignoreversion

[InstallDelete]
; 예전 버전에 들어 있던, 지금은 쓰지 않는 큰 파일들을 업데이트할 때 지운다
Type: filesandordirs; Name: "{app}\_internal\nvidia\cudnn"
Type: filesandordirs; Name: "{app}\_internal\nvidia\cuda_nvrtc"
Type: filesandordirs; Name: "{app}\_internal\av"
Type: filesandordirs; Name: "{app}\_internal\av.libs"
Type: filesandordirs; Name: "{app}\_internal\PIL"
Type: files; Name: "{app}\_internal\cublas64_13.dll"
Type: files; Name: "{app}\_internal\cublasLt64_13.dll"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\TimeZoop_tz.ico"
Name: "{group}\{#AppName} 제거"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\TimeZoop_tz.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{#AppName} 실행"; Flags: nowait postinstall skipifsilent

[Code]
// 제거할 때, 첫 실행에 받은 AI 모델·분석 데이터(%LOCALAPPDATA%\TimeZoop)도 지울지 묻는다.
// 설정·로그인 정보(%APPDATA%\TimeZoop)는 같이 지운다. 타임라인 텍스트 파일(문서\타임줍)은 사용자 결과물이라 남긴다.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DelTree(ExpandConstant('{userappdata}\{#AppNameEn}'), True, True, True);
    DataDir := ExpandConstant('{localappdata}\{#AppNameEn}');
    if DirExists(DataDir) then
      if MsgBox('AI 모델과 분석 데이터(약 10GB)도 지울까요?' + #13#10 + #13#10 +
                '다시 설치할 계획이면 남겨 두는 게 좋아요. 다시 받지 않아도 돼요.' + #13#10 +
                '만든 타임라인 텍스트 파일(문서\타임줍)은 지우지 않아요.',
                mbConfirmation, MB_YESNO) = IDYES then
        DelTree(DataDir, True, True, True);
  end;
end;
