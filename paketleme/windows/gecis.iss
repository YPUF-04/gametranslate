; SPDX-License-Identifier: AGPL-3.0-only
; AltYazıKöprüsü GEÇİŞ KURUCUSU (Inno Setup 6): eski (Inno ile kurulmuş) sürümlerden Velopack sürümüne BİR KEZ geçirir.
;
; Neden var? Eski sürümlerdeki "Güncelle" düğmesi Sürümler sayfasında `AltYaziKoprusu-Kur-<sürüm>.exe` adlı dosyayı
; arar, SHA256SUMS.txt ile doğrular ve `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /GUNCELLEME=1` ile çalıştırır.
; Bu dosya tam o adla çıkar ve içinde Velopack kurucusu (Setup.exe) taşır:
;   1) eski programı kapatır, 2) Velopack kurucusunu sessizce çalıştırır (yeni program açılır),
;   3) eski Inno kurulumunu kaldırır (kısayollar/kayıt temizlenir).
; Ayarlar, anahtarlar, oyun hafızası ve dublaj paketi KORUNUR: hiçbiri eski program klasöründe değildir
; (ayarlar %APPDATA%\AltyaziKoprusu, dublaj %LOCALAPPDATA%\AltYaziKoprusu\dublaj-ortami, anahtarlar Credential Manager);
; eski kaldırıcı sessiz çalıştığı için "veriyi sil" sorusu sorulmaz ve veri silinmez.
; Sonraki güncellemeler Velopack ile yalnız DEĞİŞEN parçaları indirir; bu dosya yalnız bir kez gerekir.
;
; Derleme: ISCC.exe /DSurum=0.3.0 /DVelopackKurucu=C:\...\AltYaziKoprusu.Program-win-Setup.exe paketleme\windows\gecis.iss

#ifndef Surum
  #define Surum "0.0.0"
#endif
#ifndef VelopackKurucu
  #error VelopackKurucu verilmedi: /DVelopackKurucu=<vpk pack'in ürettiği ...-win-Setup.exe>
#endif
#define Ad "AltYazıKöprüsü"

[Setup]
; Eski Inno kurulumunun AppId'sinden FARKLI (bu kurucu bir şey kurmaz/kaydetmez).
AppId={{D4E7A2B9-6C13-4F58-8A0E-2B91C7E5F3A6}
AppName={#Ad}
AppVersion={#Surum}
AppVerName={#Ad} {#Surum}
AppPublisher=AltYazıKöprüsü katkıcıları
SetupIconFile=..\simge\uygulama.ico
WizardImageFile=..\simge\kurulum-buyuk.bmp
WizardSmallImageFile=..\simge\kurulum-kucuk.bmp
VersionInfoVersion={#Surum}
VersionInfoProductName={#Ad}
VersionInfoDescription={#Ad} güncelleme kurucusu
VersionInfoCompany=AltYazıKöprüsü katkıcıları
PrivilegesRequired=lowest
CreateAppDir=no
Uninstallable=no
DisableProgramGroupPage=yes
DisableReadyPage=yes
LicenseFile=..\..\LICENSE
OutputDir=..\..\dist\kurulum
OutputBaseFilename=AltYaziKoprusu-Kur-{#Surum}
; İçindeki Velopack kurucusu zaten sıkıştırılmış
Compression=none
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
turkish.Kuruluyor=Yeni sürüm kuruluyor, lütfen bekleyin...
english.Kuruluyor=Installing the new version, please wait...
turkish.Hata=Yeni sürüm kurulamadı. Eski sürüm kaldırılmadı; programı olduğu gibi kullanabilirsiniz.%n%nTekrar denemek için indirme sayfasındaki "AltYaziKoprusu-Windows-Kur.exe" dosyasını çalıştırın.
english.Hata=The new version could not be installed. The old version was NOT removed and still works.%n%nTo try again run "AltYaziKoprusu-Windows-Kur.exe" from the download page.

[Files]
Source: "{#VelopackKurucu}"; DestDir: "{tmp}"; DestName: "velopack-kur.exe"; Flags: deleteafterinstall

[Code]
const
  ESKI_KAYIT = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{6B0F7C1E-3D52-4B8A-9E41-5A7C2F9D1B30}_is1';

procedure CurStepChanged(CurStep: TSetupStep);
var
  Kod: Integer;
  Eski: String;
begin
  if CurStep <> ssPostInstall then
    Exit;
  WizardForm.StatusLabel.Caption := CustomMessage('Kuruluyor');
  { 1) Çalışan eski program kapansın (kaldırırken dosyaları kilitlemesin) }
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/IM AltYaziKoprusu.exe /F', '', SW_HIDE, ewWaitUntilTerminated, Kod);
  { 2) Velopack kurucusu: yeni programı kurar ve açar }
  if (not Exec(ExpandConstant('{tmp}\velopack-kur.exe'), '--silent', '', SW_HIDE, ewWaitUntilTerminated, Kod)) or (Kod <> 0) then
  begin
    SuppressibleMsgBox(CustomMessage('Hata'), mbError, MB_OK, IDOK);
    Exit;   { eski sürüm yerinde kalır }
  end;
  { 3) Eski Inno kurulumunu kaldır; sessiz olduğu için kullanıcı verisi SİLİNMEZ }
  if RegQueryStringValue(HKCU, ESKI_KAYIT, 'UninstallString', Eski) then
    Exec(RemoveQuotes(Eski), '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART', '', SW_HIDE, ewWaitUntilTerminated, Kod);
end;
