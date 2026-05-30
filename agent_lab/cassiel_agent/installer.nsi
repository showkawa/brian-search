; Cassiel Agent — NSIS Installer Script
; ========================================
; Build with:
;   makensis installer.nsi
;
; Prerequisites:
;   - NSIS 3.x installed (https://nsis.sourceforge.io)
;   - dist/CassielAgent/ directory populated by PyInstaller or Nuitka
;
; Output:
;   CassielAgent-Setup-0.1.0.exe

; ── Installer metadata ───────────────────────────────────────
!define APP_NAME        "Cassiel Agent"
!define APP_EXE         "CassielAgent.exe"
!define APP_VERSION     "0.1.0"
!define APP_PUBLISHER   "Cassiel"
!define APP_URL         "https://github.com/cassiel/agent"
!define APP_REG_KEY     "Software\Cassiel\CassielAgent"
!define APP_UNINSTALLER "Uninstall.exe"

; ── Source directory (PyInstaller/Nuitka output) ─────────────
!define DIST_DIR        "dist\CassielAgent"

; ── NSIS settings ────────────────────────────────────────────
Unicode          True
SetCompressor    /SOLID lzma
InstallDir       "$PROGRAMFILES\${APP_NAME}"
InstallDirRegKey HKLM "${APP_REG_KEY}" "InstallDir"
Name             "${APP_NAME} ${APP_VERSION}"
OutFile          "CassielAgent-Setup-${APP_VERSION}.exe"
RequestExecutionLevel admin

; ── Modern UI ────────────────────────────────────────────────
!include "MUI2.nsh"
!define MUI_ICON         "None"    ; TODO: add .ico
!define MUI_UNICON       "None"    ; TODO: add .ico
!define MUI_WELCOMEFINISHPAGE_BITMAP "None" ; TODO: add .bmp

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES

; Offer to launch after install
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Launch ${APP_NAME}"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"

; ── Version info ─────────────────────────────────────────────
VIProductVersion "${APP_VERSION}.0"
VIAddVersionKey /LANG=0 "ProductName"     "${APP_NAME}"
VIAddVersionKey /LANG=0 "ProductVersion"  "${APP_VERSION}"
VIAddVersionKey /LANG=0 "CompanyName"     "${APP_PUBLISHER}"
VIAddVersionKey /LANG=0 "FileDescription" "${APP_NAME} Installer"
VIAddVersionKey /LANG=0 "FileVersion"     "${APP_VERSION}"

; ══════════════════════════════════════════════════════════════
; Sections
; ══════════════════════════════════════════════════════════════

Section "!${APP_NAME}" SecMain
    SectionIn RO

    SetOutPath "$INSTDIR"

    ; Copy entire dist directory
    File /r "${DIST_DIR}\*.*"

    ; Write uninstaller
    WriteUninstaller "$INSTDIR\${APP_UNINSTALLER}"

    ; Registry — uninstall entry
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "DisplayName"   "${APP_NAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "DisplayVersion" "${APP_VERSION}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "Publisher"     "${APP_PUBLISHER}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "UninstallString" '"$INSTDIR\${APP_UNINSTALLER}"'
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "InstallLocation" "$INSTDIR"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "URLInfoAbout"  "${APP_URL}"
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "NoModify" 1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "NoRepair" 1

    ; Registry — install path for upgrade detection
    WriteRegStr HKLM "${APP_REG_KEY}" "InstallDir" "$INSTDIR"

    ; Calculate installed size
    ${GetSize} "$INSTDIR" "/S=0K" $0
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "EstimatedSize" "$0"
SectionEnd

; ── Desktop shortcut ─────────────────────────────────────────
Section "Desktop Shortcut" SecDesktop
    CreateShortCut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
SectionEnd

; ── Start Menu ───────────────────────────────────────────────
Section "Start Menu Entry" SecStartMenu
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortCut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"   "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
    CreateShortCut "$SMPROGRAMS\${APP_NAME}\Uninstall.lnk"     "$INSTDIR\${APP_UNINSTALLER}"
SectionEnd

; ── Section descriptions ─────────────────────────────────────
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SecMain}      "Install ${APP_NAME} (required)"
    !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop}   "Create a desktop shortcut"
    !insertmacro MUI_DESCRIPTION_TEXT ${SecStartMenu} "Create a Start Menu entry"
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; ══════════════════════════════════════════════════════════════
; Uninstaller
; ══════════════════════════════════════════════════════════════

Section "Uninstall"
    ; Remove files
    RMDir /r "$INSTDIR"

    ; Remove shortcuts
    Delete "$DESKTOP\${APP_NAME}.lnk"
    RMDir /r "$SMPROGRAMS\${APP_NAME}"

    ; Remove registry keys
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
    DeleteRegKey HKLM "${APP_REG_KEY}"
SectionEnd

; ── Helper: get folder size ──────────────────────────────────
!macro GetSize DIR RESULT
    System::Call 'kernel32::GetDiskFreeSpaceEx(t "${DIR}", *l .r0, *l .r1, *l .r2) i .r3'
    StrCpy ${RESULT} $0
!macroend

; ── Callbacks ────────────────────────────────────────────────
Function .onInit
    ; Default: check both optional sections
    !insertmacro MUI_LANGDLL_DISPLAY
FunctionEnd
