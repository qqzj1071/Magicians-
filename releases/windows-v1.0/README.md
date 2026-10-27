# Magicians! v1.0 · Windows 免安装试玩包

这是已导出的游戏程序，供玩家直接下载试玩。

## 下载与启动

1. 下载 [Magicians-v1.0-Windows-x64.zip](https://github.com/qqzj1071/Magicians-/raw/refs/heads/v1.0/releases/windows-v1.0/Magicians-v1.0-Windows-x64.zip)（约 81 MiB）。
2. 将整个压缩包解压到一个文件夹。
3. 打开解压后的 `Magicians-2026.10.27-Windows` 文件夹，双击 `Magicians.exe`。
4. 点击“开始单人赛事”。

玩家不需要另外安装 Godot、Python 或 .NET；单人 AI 对战无需联网。
适用平台：64 位 Windows 10/11（Intel/AMD x64）。

请保留 EXE 旁的 `Magicians.pck`、`data_Magicians!_windows_x86_64`、`runtime-data` 等文件。
不能只拷贝一个 EXE；需要桌面入口时，为 EXE 创建快捷方式即可。

## 校验

- 文件大小：84,795,845 字节。
- SHA-256：`9044bf02480964b6c67a29c738a3a2055a7d7adc66ccdc9188630f0128ae921e`。
- 独立校验文件：[SHA256SUMS.txt](SHA256SUMS.txt)。
- 包内另有 `MANIFEST.sha256`，记录各文件的 SHA-256。

## 内容与验证

打包日期：2026-10-27。包含 Godot 4.7.2 .NET Windows x64 Release 程序、
.NET 自包含运行时、Python 3.12.10 便携运行时、现行规则数据及指定 AI 模型。
未调整现行卡牌、构筑规则或 AI 模型。美术仍是当前开发版的占位素材。

已在当前电脑中屏蔽全局 Python/.NET 路径、迁移到中文及空格目录，
从独立工作目录验证导出的 EXE：主菜单、开始赛事、真实 AI 构筑/战斗及两轮结算通过；
图形模式下核对了主菜单和构筑界面。尚未在另一台实体电脑上验证。
更多内容见压缩包内的 `开始游玩.txt` 和 `验证说明.txt`。

此目录发布预编译游戏包；仓库根目录的源码仍按原有开发流程使用。
