# Magicians! v1.0 Windows 安装包

当前正式发布方式为 `build_portable.py` 生成的免安装 ZIP，玩家解压后双击 EXE。见 `docs/client/portable-release.md`。下方旧 PowerShell 安装器保留供历史参考，不作为当前试玩分发入口；旧“复制临时目录”方案并不能防外挂。

运行 `Install-Magicians.ps1` 会把客户端安装到 `%LOCALAPPDATA%\Magicians!`，并在桌面创建快捷方式。安装包包含客户端、Godot 启动配置和卡牌 DOCX；缺少 Godot 或 Python 时，启动器会下载固定版本并继续启动。

每次启动都会从只读客户端副本创建临时运行目录，游戏结束后删除临时目录，避免直接修改安装包中的游戏文件。该机制用于防止普通文件篡改，不替代服务器端反作弊。

