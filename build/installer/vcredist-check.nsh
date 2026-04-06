; VC++ Redistributable 静默安装（NSIS include 脚本）
; electron-builder 的 nsis.include 配置引用此文件
;
; 安装流程：
;   1. 检测注册表判断 VC++ 14.x 是否已安装
;   2. 若未安装，释放捆绑的 vc_redist.x64.exe 并静默安装
;   3. 安装完成后清理临时文件
;
; 前置条件：
;   将 vc_redist.x64.exe 放在 build/installer/ 目录下，
;   并在 package.json build.nsis.extraFiles 中配置。

!macro customInstall
  ; 检查 VC++ 14.x (2015-2022) 是否已安装
  ReadRegDWORD $0 HKLM "SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64" "Installed"
  ${If} $0 != 1
    DetailPrint "正在安装 Visual C++ 运行时库..."
    File "/oname=$PLUGINSDIR\vc_redist.x64.exe" "${BUILD_RESOURCES_DIR}\vc_redist.x64.exe"
    ExecWait '"$PLUGINSDIR\vc_redist.x64.exe" /install /quiet /norestart' $1
    DetailPrint "VC++ Redistributable 安装退出码: $1"
    Delete "$PLUGINSDIR\vc_redist.x64.exe"
  ${Else}
    DetailPrint "VC++ Redistributable 已安装，跳过"
  ${EndIf}
!macroend
