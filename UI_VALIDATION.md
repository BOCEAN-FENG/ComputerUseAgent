# 界面验证记录

日期：2026-10-19。平台：Linux，PySide6-Essentials 6.12，Fusion，Qt offscreen。截图使用本地 Noto Sans CJK SC；Windows 运行时使用 Segoe UI 与微软雅黑回退。

| 检查 | 结果 |
| --- | --- |
| 1440×900 浅色、深色工作区 | 已启动真实 Qt 控件并查看渲染截图 |
| 1024×768、980×700 | 观察面板自动收起，主操作可见 |
| Qt 125% / 150% 缩放 | 最小窗口尺寸及主操作可见性通过（离屏） |
| 独立屏幕观察 | 面板切换及返回工作区通过 |
| 模型配置、密钥显隐、运行选项 | 离线界面测试通过 |
| API 响应与用户回复 | 已检查最小窗口截图，内部内容可滚动 |
| 启动→等待回复→提交回复→完成；再次启动→停止 | Qt 信号与离线执行替身验证通过 |
| 长中文草稿、预览图片缩放、日志滚动跟随 | 界面测试通过 |
| 原有回归测试 | 52 项通过 |
| 新增原生界面测试 | 5 项通过 |
| 技能调色板检查 | 72 组对比度检查通过；此项只验证基线色值 |

运行回归：

```powershell
python -m unittest discover -s tests -q
$env:QT_QPA_PLATFORM = 'offscreen'
python tests/ui_smoke.py
Remove-Item Env:QT_QPA_PLATFORM
```

界面测试使用临时偏好文件与离线 Agent 替身，不会请求服务商或发送真实键鼠操作。`previews` 中为真实 Qt 控件离屏截图，不是设计稿；API 视图截图使用空会话目录。

未验证：真实 Windows 11 窗口管理、托盘与全局热键、Windows 字体回退、EXE 构建与运行、连接真实模型后对实际桌面的完整控制流程。原有 engine.py / worker.py 等执行文件保持不变，本次离线测试不替代 Windows 端验收。
