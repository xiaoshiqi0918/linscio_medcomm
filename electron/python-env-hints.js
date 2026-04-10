/**
 * 根据 Windows 下嵌入 Python 的 stderr / exit code 推断环境问题。
 *
 * 常见 Windows NTSTATUS exit codes（python.exe 加载 DLL 失败时直接返回）：
 *   0xC0000135 (-1073741515) = STATUS_DLL_NOT_FOUND
 *   0xC000007B (-1073741189) = STATUS_INVALID_IMAGE_FORMAT (x86/x64 不匹配)
 *   0xC0000142 (-1073741502) = STATUS_DLL_INIT_FAILED
 */

const DLL_EXIT_CODES = {
  '-1073741515': 'STATUS_DLL_NOT_FOUND — 缺少必要的 DLL（通常是 vcruntime140.dll）',
  '-1073741189': 'STATUS_INVALID_IMAGE_FORMAT — 架构不匹配（可能安装了 x86 版 VC++ 而非 x64）',
  '-1073741502': 'STATUS_DLL_INIT_FAILED — DLL 初始化失败（运行库损坏或版本冲突）',
}

const VCREDIST_REPAIR_HINT =
  '请按以下步骤操作：\n'
  + '1. 下载官方 VC++ 2015-2022 x64：https://aka.ms/vs/17/release/vc_redist.x64.exe\n'
  + '2. 运行安装程序，如果出现「修复」按钮请选修复，如果出现「安装」请安装\n'
  + '3. 完成后 **重启电脑**（不是关机再开，是重启）\n'
  + '4. 重启后再打开 LinScio MedComm\n\n'
  + '注意：必须安装 x64 版本，不能只装 x86。'

function windowsPythonStderrCategory(stderr) {
  const s = String(stderr || '').toLowerCase()
  if (!s) return { category: 'unknown', extraHint: '' }

  if (
    /vcruntime140|msvcp140|vcomp140|mfc140|api-ms-win-crt|0xc000007b|the application was unable to start correctly/.test(s)
  ) {
    return { category: 'vcredist', extraHint: VCREDIST_REPAIR_HINT }
  }

  return { category: 'other', extraHint: '' }
}

/**
 * 基于 exit code 判断是否为 DLL/运行库问题（stderr 为空时的兜底）。
 */
function windowsExitCodeCategory(exitCode) {
  if (exitCode == null) return { category: 'unknown', extraHint: '' }
  const key = String(exitCode)
  const desc = DLL_EXIT_CODES[key]
  if (desc) {
    return {
      category: 'vcredist',
      extraHint: `Windows 错误：${desc}\n\n${VCREDIST_REPAIR_HINT}`,
    }
  }
  const unsigned = exitCode < 0 ? (exitCode >>> 0) : exitCode
  const hex = unsigned.toString(16).toUpperCase()
  if (hex.startsWith('C0000')) {
    return {
      category: 'vcredist_likely',
      extraHint:
        `Windows 系统错误 0x${hex}，很可能与运行库有关。\n\n${VCREDIST_REPAIR_HINT}`,
    }
  }
  return { category: 'unknown', extraHint: '' }
}

module.exports = { windowsPythonStderrCategory, windowsExitCodeCategory, VCREDIST_REPAIR_HINT }
