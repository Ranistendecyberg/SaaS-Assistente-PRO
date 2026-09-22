[Setup]
; Identificação do App
AppName=SaaS Assistente PRO
AppId=SaaS Assistente PRO
AppVersion=2.1.8
AppPublisher=Gestao de Qualidade
AppCopyright=Copyright (C) 2026

; Instalação por usuário: não exibe UAC durante atualizações automáticas.
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\SaaS Assistente PRO
UsePreviousAppDir=yes
DefaultGroupName=SaaS Assistente PRO
CloseApplications=force
CloseApplicationsFilter=SaaS Assistente PRO.exe
RestartApplications=no
AppMutex=SaaSAssistentePRO.MainWindow
LicenseFile=src\assets\termos_de_uso.txt

; Ícones e Visual
SetupIconFile=logo.ico
UninstallDisplayIcon={app}\SaaS Assistente PRO.exe
Compression=lzma2/ultra
SolidCompression=yes
OutputDir=dist
OutputBaseFilename=Instalador_SaaS_Assistente_PRO_v2.1.8

[Tasks]
Name: "desktopicon"; Description: "Criar um atalho na Área de Trabalho"; GroupDescription: "Atalhos adicionais:"; Flags: checkedonce

[Files]
; Copia o executável principal e o ícone para a pasta de instalação
Source: "dist\SaaS Assistente PRO v2.1.8.exe"; DestDir: "{app}"; DestName: "SaaS Assistente PRO.exe"; Flags: ignoreversion
Source: "logo.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Atalhos no Menu Iniciar e Desktop
Name: "{group}\SaaS Assistente PRO"; Filename: "{app}\SaaS Assistente PRO.exe"; IconFilename: "{app}\logo.ico"
Name: "{autodesktop}\SaaS Assistente PRO"; Filename: "{app}\SaaS Assistente PRO.exe"; IconFilename: "{app}\logo.ico"; Tasks: desktopicon

[Run]
; Instalação manual: permite ao usuário escolher se deseja abrir o sistema.
; Em atualizações silenciosas, o Assistente de Atualização reabre o Desktop
; somente depois que o instalador termina com sucesso.
Filename: "{app}\SaaS Assistente PRO.exe"; Description: "Iniciar SaaS Assistente PRO agora"; Flags: nowait postinstall skipifsilent
