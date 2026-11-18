; SPDX-License-Identifier: AGPL-3.0-only
; AltYazıKöprüsü Windows kurucusu (Inno Setup 6). Yönetici izni GEREKTİRMEZ (kullanıcı başına kurulum).
; Derleme: ISCC.exe /DSurum=0.2.0 paketleme\windows\kurulum.iss   (önce PyInstaller ile dist\AltYaziKoprusu üretilir)
; Güncelleme: program yeni kurucuyu /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /GUNCELLEME=1 ile çalıştırır;
;            /GUNCELLEME=1 varsa kurulum bitince program kendiliğinden yeniden açılır.

#ifndef Surum
  #define Surum "0.0.0"
#endif
#define Ad "AltYazıKöprüsü"
#define Exe "AltYaziKoprusu.exe"

[Setup]
; Bu kimlik HİÇ değişmemeli: aynı kimlik = güncelleme eskisinin üstüne kurulur.
AppId={{6B0F7C1E-3D52-4B8A-9E41-5A7C2F9D1B30}
AppName={#Ad}
AppVersion={#Surum}
AppVerName={#Ad} {#Surum}
AppPublisher=AltYazıKöprüsü katkıcıları
AppPublisherURL=https://github.com/YPUF-04/gametranslate
AppSupportURL=https://github.com/YPUF-04/gametranslate/issues
AppUpdatesURL=https://github.com/YPUF-04/gametranslate/releases
VersionInfoVersion={#Surum}
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\AltYaziKoprusu
DefaultGroupName={#Ad}
DisableProgramGroupPage=yes
UninstallDisplayName={#Ad}
UninstallDisplayIcon={app}\{#Exe}
LicenseFile=..\..\LICENSE
OutputDir=..\..\dist\kurulum
OutputBaseFilename=AltYaziKoprusu-Kur-{#Surum}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
turkish.ProgramiBaslat=Programı şimdi başlat
english.ProgramiBaslat=Start the program now
turkish.MasaustuKisayolu=Masaüstüne kısayol koy
english.MasaustuKisayolu=Create a desktop shortcut
turkish.VeriyiSilSoru=Ayarlarınız ve oyun hafızanız da silinsin mi?%n%n"Hayır" derseniz bunlar bilgisayarda kalır ve programı sonra yeniden kurarsanız geri gelir.
english.VeriyiSilSoru=Delete your settings and game memory too?%n%nIf you choose "No" they stay on this computer and come back if you install the program again.

[Tasks]
Name: "masaustu"; Description: "{cm:MasaustuKisayolu}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\..\dist\AltYaziKoprusu\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\NOTICE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#Ad}"; Filename: "{app}\{#Exe}"
Name: "{group}\{cm:UninstallProgram,{#Ad}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#Ad}"; Filename: "{app}\{#Exe}"; Tasks: masaustu

[Run]
; Elle kurulumda son sayfadaki "Programı şimdi başlat" kutusu
Filename: "{app}\{#Exe}"; Description: "{cm:ProgramiBaslat}"; Flags: nowait postinstall skipifsilent
; Güncelleme (sessiz) kurulumunda program kendiliğinden yeniden açılır
Filename: "{app}\{#Exe}"; Flags: nowait; Check: GuncellemeMi

[Code]
function GuncellemeMi: Boolean;
begin
  Result := ExpandConstant('{param:GUNCELLEME|0}') = '1';
end;

{ Kaldırırken kullanıcı verisi (ayarlar + oyun hafızası) varsayılan olarak KORUNUR; yalnız "Evet" denirse silinir.
  Sessiz kaldırmada soru sorulmaz ve veri korunur. }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Veri: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    Veri := ExpandConstant('{userappdata}\AltyaziKoprusu');
    if DirExists(Veri) then
      if SuppressibleMsgBox(CustomMessage('VeriyiSilSoru'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES then
        DelTree(Veri, True, True, True);
  end;
end;
