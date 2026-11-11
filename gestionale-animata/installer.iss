; Installatore Windows del gestionale agende.
;
; Si compila con Inno Setup 6 (gratuito, https://jrsoftware.org/isdl.php),
; con CREA_SETUP.bat oppure a mano:
;     "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
; Prima va creato dist\Gestionale.exe con CREA_EXE.bat.
;
; Il risultato e' Output\GestionaleAgende-animata-setup.exe, l'unico file da portare
; sul PC della segreteria: doppio clic, avanti, fine. E' uguale per tutte le
; sedi: nome, logo e colori si impostano dal programma, struttura per struttura.
;
; Installa per l'utente che lo lancia, senza diritti di amministratore. Con
; i diritti di amministratore collegamenti e avvio automatico finirebbero nel
; profilo di chi ha digitato la password, non in quello di chi usa il programma.
;
; File salvato in UTF-8 con BOM: senza, Inno Setup lo legge nella codifica di
; sistema e le lettere accentate dei messaggi escono storpiate.

#define NomeApp "Gestionale Agende"
#define Versione "1.12.6"
#define Editore "Gruppo NefroCenter"
#define Eseguibile "Gestionale.exe"

[Setup]
AppId={{7A3C1E64-9B2D-4F58-A0E7-3D5C81B4F210}
AppName={#NomeApp}
AppVersion={#Versione} animata
AppVerName={#NomeApp} {#Versione} (con animazioni)
AppPublisher={#Editore}
VersionInfoVersion={#Versione}
VersionInfoCompany={#Editore}
VersionInfoDescription=Installazione {#NomeApp}
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#NomeApp}
DefaultGroupName={#NomeApp}
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
; la pagina di benvenuto serve solo quando il gestionale c'e' gia' (aggiornamento o
; dati gia' presenti): ShouldSkipPage la salta nelle installazioni nuove
DisableWelcomePage=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=Output
OutputBaseFilename=GestionaleAgende-animata-setup
SetupIconFile=static\icona.ico
WizardSmallImageFile=installatore\setup-piccola.bmp,installatore\setup-piccola-2x.bmp
; pagina finale: la stessa icona del programma al posto della scatola di serie
WizardImageFile=installatore\setup-grande.bmp,installatore\setup-grande-2x.bmp
UninstallDisplayIcon={app}\{#Eseguibile}
UninstallDisplayName={#NomeApp}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; il programma gira in background e va chiuso prima di sostituirne il file:
; lo fa ChiudiGestionale qui sotto, in modo deterministico
CloseApplications=no

[Languages]
Name: "italiano"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "Icona ""Agende"" sul desktop"; GroupDescription: "Collegamenti:"
Name: "avvioautomatico"; Description: "Avvia il gestionale all'accesso a Windows, in silenzio"; GroupDescription: "Avvio:"

[Files]
Source: "dist\{#Eseguibile}"; DestDir: "{app}"; Flags: ignoreversion
Source: "BACKUP.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "FERMA.bat"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#NomeApp}"; Filename: "{app}\{#Eseguibile}"; Comment: "Agenda delle stanze"
Name: "{autodesktop}\Agende"; Filename: "{app}\{#Eseguibile}"; Comment: "Agenda delle stanze"; Tasks: desktopicon
; all'accesso parte senza aprire il browser: la pagina la apre l'icona Agende
Name: "{userstartup}\{#NomeApp}"; Filename: "{app}\{#Eseguibile}"; Parameters: "--avvio-automatico"; Tasks: avvioautomatico

[Run]
Filename: "{app}\{#Eseguibile}"; Description: "Apri il gestionale adesso"; Flags: nowait postinstall skipifsilent
; «Aggiorna adesso» avvia questo Setup senza domande (/SILENT): alla fine il gestionale
; si riapre da solo, senza aprire un'altra pagina del browser. Quella rimasta aperta
; aspetta che torni e mostra le novita'
Filename: "{app}\{#Eseguibile}"; Parameters: "--avvio-automatico"; Flags: nowait; Check: WizardSilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /T /IM {#Eseguibile}"; Flags: runhidden; RunOnceId: "ChiudiGestionale"

; Il database e il registro stanno in %LOCALAPPDATA%\GestionaleAgende e non
; vengono toccati: ne' dall'aggiornamento ne' dalla disinstallazione.
; E' voluto. Cancellarli va fatto a mano, e solo dopo averne messo via una copia.

[Code]
const
  { la chiave che Inno Setup scrive per questo AppId: c'e' la versione installata }
  ChiaveInstallazione = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{7A3C1E64-9B2D-4F58-A0E7-3D5C81B4F210}_is1';
  { questa versione, come la vede Windows ("1.5", oppure "1.5 animata") }
  QuestaVersione = '{#SetupSetting("AppVersion")}';

var
  VersionePrecedente: String;
  DatiPresenti: Boolean;

function LeggiVersionePrecedente(): String;
begin
  Result := '';
  if not RegQueryStringValue(HKCU, ChiaveInstallazione, 'DisplayVersion', Result) then
    if not RegQueryStringValue(HKLM, ChiaveInstallazione, 'DisplayVersion', Result) then
      Result := '';
  Result := Trim(Result);
end;

{ "1.4.6 animata" -> "1.4.6": dopo lo spazio c'e' la variante, non un numero }
function SoloNumeri(Versione: String): String;
var
  Spazio: Integer;
begin
  Result := Trim(Versione);
  Spazio := Pos(' ', Result);
  if Spazio > 0 then
    Result := Copy(Result, 1, Spazio - 1);
end;

{ il primo numero di una versione "1.4.6", tolto dalla stringa }
function PrimoNumero(var Testo: String): Integer;
var
  Punto: Integer;
begin
  Punto := Pos('.', Testo);
  if Punto = 0 then
  begin
    Result := StrToIntDef(Trim(Testo), 0);
    Testo := '';
  end
  else
  begin
    Result := StrToIntDef(Trim(Copy(Testo, 1, Punto - 1)), 0);
    Delete(Testo, 1, Punto);
  end;
end;

{ -1, 0, 1: "1.4.6" contro "1.5" numero per numero }
function ConfrontaVersioni(A, B: String): Integer;
var
  X, Y: Integer;
begin
  A := SoloNumeri(A);
  B := SoloNumeri(B);
  Result := 0;
  while (Result = 0) and ((A <> '') or (B <> '')) do
  begin
    X := PrimoNumero(A);
    Y := PrimoNumero(B);
    if X < Y then
      Result := -1
    else if X > Y then
      Result := 1;
  end;
end;

procedure InitializeWizard();
var
  Cartella, Restano: String;
  Confronto: Integer;
begin
  VersionePrecedente := LeggiVersionePrecedente();
  Cartella := ExpandConstant('{localappdata}\GestionaleAgende');
  DatiPresenti := FileExists(Cartella + '\agende.db');
  Restano := 'Non serve disinstallare niente: appuntamenti, pazienti, documenti e impostazioni restano dove sono.';
  if VersionePrecedente <> '' then
  begin
    WizardForm.WelcomeLabel1.Caption := 'Aggiornamento del {#NomeApp}';
    Confronto := ConfrontaVersioni(VersionePrecedente, QuestaVersione);
    if Confronto < 0 then
      WizardForm.WelcomeLabel2.Caption :=
        'È installata la versione ' + VersionePrecedente + ': verrà aggiornata alla ' + QuestaVersione + '.' + #13#10#13#10 +
        Restano + ' Se la versione nuova cambia il database, al primo avvio il programma ne fa prima una copia.' + #13#10#13#10 +
        'Se il gestionale è aperto viene chiuso, e alla fine si riapre.'
    else if (Confronto = 0) and (CompareText(VersionePrecedente, QuestaVersione) = 0) then
      WizardForm.WelcomeLabel2.Caption :=
        'La versione ' + QuestaVersione + ' è già installata: verrà installata di nuovo, per esempio per riparare il programma.' + #13#10#13#10 +
        Restano
    else if Confronto = 0 then
      WizardForm.WelcomeLabel2.Caption :=
        'È installata la versione ' + VersionePrecedente + ': verrà sostituita dalla ' + QuestaVersione + '.' + #13#10#13#10 +
        Restano + #13#10#13#10 + 'Se il gestionale è aperto viene chiuso, e alla fine si riapre.'
    else
      WizardForm.WelcomeLabel2.Caption :=
        'Attenzione: è installata la versione ' + VersionePrecedente + ', più nuova di questa (' + QuestaVersione + ').' + #13#10#13#10 +
        'Continuando si torna alla ' + QuestaVersione + '. I dati restano, ma quello che c''è solo nella ' +
        'versione più nuova non si vedrà finché non la si reinstalla. Se non è voluto, premere Annulla.';
  end
  else if DatiPresenti then
  begin
    WizardForm.WelcomeLabel1.Caption := 'Installazione del {#NomeApp} ' + QuestaVersione;
    WizardForm.WelcomeLabel2.Caption :=
      'Su questo PC ci sono già appuntamenti salvati, in ' + Cartella + '.' + #13#10#13#10 +
      'Il programma li ritrova tutti: non vengono toccati.';
  end;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  { installazione nuova: si parte dalle scelte, come prima }
  Result := (PageID = wpWelcome) and (VersionePrecedente = '') and (not DatiPresenti);
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = wpFinished) and (VersionePrecedente <> '') then
    WizardForm.FinishedLabel.Caption :=
      'Il {#NomeApp} è alla versione ' + QuestaVersione + '. Appuntamenti, pazienti e impostazioni sono rimasti dove erano.';
end;

procedure ChiudiGestionale();
var
  Codice: Integer;
begin
  { se e' aperto il file e' in uso e non si puo' sostituire; /T chiude anche il
    processo figlio che l'eseguibile a file unico avvia: senza, uno dei due resta
    e tiene il file (provato nel Windows finto alla 1.11). Il browser aperto dal
    gestionale qui non c'e': il Setup lo lancia Aggiorna adesso dal programma }
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM {#Eseguibile}', '',
       SW_HIDE, ewWaitUntilTerminated, Codice);
  Sleep(700);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  ChiudiGestionale();
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
    MsgBox('Il gestionale è stato rimosso.' + #13#13 +
      'Gli appuntamenti NON sono stati cancellati: restano in' + #13 +
      ExpandConstant('{localappdata}\GestionaleAgende') + #13#13 +
      'Reinstallando il programma li ritrova tutti.',
      mbInformation, MB_OK);
end;
