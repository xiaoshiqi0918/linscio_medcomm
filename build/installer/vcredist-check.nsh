; VC++ Redistributable 安装 / 修复（NSIS include 脚本）
; electron-builder 的 nsis.include 配置引用此文件
;
; 检测逻辑：
;   1. 检查注册表判断 VC++ 14.x 是否已安装
;   2. 即使注册表标记已装，也验证关键 DLL 是否存在（防止损坏/残留注册表）
;   3. 若未安装或 DLL 缺失，释放捆绑的 vc_redist.x64.exe 并静默安装
;   4. 检查安装退出码，若失败则弹窗提醒

!macro customInstall
  ; 检查 VC++ 14.x (2015-2022) 注册表
  ReadRegDWORD $0 HKLM "SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64" "Installed"

  ; 即使注册表说已装，也验证关键 DLL 实际存在
  ; vcruntime140_1.dll 是 VC++ 14.2x (VS2019+) 新增，Python 3.11 (MSVC 2022) 依赖它
  StrCpy $2 "0"  ; 0 = DLL OK, 1 = DLL missing
  ${If} $0 == 1
    IfFileExists "$SYSDIR\vcruntime140.dll" +2 0
      StrCpy $2 "1"
    IfFileExists "$SYSDIR\vcruntime140_1.dll" +2 0
      StrCpy $2 "1"
    IfFileExists "$SYSDIR\msvcp140.dll" +2 0
      StrCpy $2 "1"
  ${EndIf}

  ${If} $0 != 1
  ${OrIf} $2 == "1"
    ${If} $2 == "1"
      DetailPrint "VC++ 注册表标记已安装，但关键 DLL 缺失，尝试修复..."
    ${Else}
      DetailPrint "正在安装 Visual C++ 运行时库..."
    ${EndIf}

    File "/oname=$PLUGINSDIR\vc_redist.x64.exe" "${BUILD_RESOURCES_DIR}\vc_redist.x64.exe"
    ExecWait '"$PLUGINSDIR\vc_redist.x64.exe" /install /quiet /norestart' $1
    DetailPrint "VC++ Redistributable 安装退出码: $1"
    Delete "$PLUGINSDIR\vc_redist.x64.exe"

    ; 检查安装结果
    ; 0    = 成功
    ; 1638 = 已安装同版本或更高版本（无需操作）
    ; 3010 = 安装成功但需要重启
    ${If} $1 == 0
    ${OrIf} $1 == 1638
      DetailPrint "VC++ Redistributable 安装/验证成功 (退出码 $1)"
    ${ElseIf} $1 == 3010
      MessageBox MB_OK|MB_ICONINFORMATION \
        "Visual C++ 运行库已安装，但需要重启电脑才能生效。$\n\
        请在安装完成后重启电脑再打开应用。"
    ${Else}
      MessageBox MB_OK|MB_ICONEXCLAMATION \
        "Visual C++ 运行库安装未成功（退出码 $1）。$\n$\n\
        应用可能无法正常运行。请在安装完成后手动安装：$\n\
        https://aka.ms/vs/17/release/vc_redist.x64.exe$\n$\n\
        安装后请重启电脑。"
    ${EndIf}
  ${Else}
    DetailPrint "VC++ Redistributable 已安装且 DLL 完整，跳过"
  ${EndIf}
!macroend
