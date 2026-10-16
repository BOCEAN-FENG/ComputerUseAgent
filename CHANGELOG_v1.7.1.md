# v1.7.1 · 修复 Win11 首次依赖安装失败

## 问题

项目位于较长路径时，PySide6 安装过程可能触发传统 Windows 260 字符路径限制。此前启动脚本把 `.venv` 放在项目目录下，并且只检查 `pythonw.exe` 是否存在，安装失败后再次启动可能跳过安装。

## 修复

- 将 `PySide6>=6.8,<7` 改为 `PySide6-Essentials>=6.8,<7`。项目仅使用 QtCore/QtGui/QtWidgets，无需安装 Qt WebEngine、PDF 和 Addons。
- 虚拟环境统一设在 `%LOCALAPPDATA%\AuroraStudio\venv`，显著缩短 PySide6 解压后的完整路径；支持 `AURORA_VENV_DIR` 覆盖。
- 启动时验证核心依赖是否真的可导入；检测安装成功标记。安装中断后下次重新尝试，而不是静默跳过。
- `build_exe.bat` 使用与启动器相同的虚拟环境路径。
- 不再每次创建虚拟环境都强制升级 pip，减少安装步骤；保留 PyPI 二进制轮子优先。

## 使用

直接运行 `launch_win11.bat`。新版**不再使用项目目录中的 `.venv`**；如果之前安装失败，你可以手动删除旧 `.venv` 以节省空间。以前的用户配置不受影响。

如果你的 Windows 用户目录特别长，仍然报长路径，请在 **PowerShell** 里执行：

```powershell
$env:AURORA_VENV_DIR = 'D:\AuVenv'
.\launch_win11.bat
```

切换版本或修改依赖时会验证新的成功标记。环境变量设置只对当前终端有效。

**测试说明**：已检查依赖导入范围、批处理脚本的路径一致性与静态结构，并运行项目的离线单元测试。未在 Windows 11 机器上执行真实的 PySide6 安装和 GUI 启动。
