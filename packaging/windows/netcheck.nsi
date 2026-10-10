!define PRODUCT_NAME "netcheck"
!define PRODUCT_VERSION "{version}"
!define PRODUCT_PUBLISHER "Network Tools Team"
!define PRODUCT_WEB_SITE "https://github.com/farman20ali/netcheck"
!define ICON_FILE "{repo_root}\assets\icons\icon.ico"

SetCompressor lzma

Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "{repo_root}\dist\win\netcheck-${PRODUCT_VERSION}-setup.exe"
InstallDir "$PROGRAMFILES64\${PRODUCT_NAME}"
RequestExecutionLevel admin

; Installer icon (shown in the NSIS wizard and Add/Remove Programs)
Icon "${ICON_FILE}"
UninstallIcon "${ICON_FILE}"

Page directory
Page instfiles

Section "Install"
    SetOutPath "$INSTDIR"
    File "{repo_root}\dist\win\netcheck.exe"
    File "${ICON_FILE}"
    
    WriteUninstaller "$INSTDIR\uninstall.exe"
    
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayName"    "${PRODUCT_NAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "UninstallString" '"$INSTDIR\uninstall.exe"'
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayVersion"  "${PRODUCT_VERSION}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "Publisher"       "${PRODUCT_PUBLISHER}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "URLInfoAbout"    "${PRODUCT_WEB_SITE}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayIcon"     "$INSTDIR\icon.ico"

    ; Add to system PATH (using registry)
    ReadRegStr $0 HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" "Path"
    WriteRegExpandStr HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" "Path" "$0;$INSTDIR"
    
    ; Broadcast environment change so PATH is picked up without rebooting
    ; HWND_BROADCAST=65535, WM_SETTINGCHANGE=0x001A, wParam=0, lParam="Environment"
    SendMessage 65535 26 0 "STR:Environment" /TIMEOUT=5000
SectionEnd

Section "Uninstall"
    Delete "$INSTDIR\netcheck.exe"
    Delete "$INSTDIR\icon.ico"
    Delete "$INSTDIR\uninstall.exe"
    RMDir  "$INSTDIR"
    
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
SectionEnd
