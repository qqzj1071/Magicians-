# Magicians!

当前项目版本：**v1.1.2**。

已经完成火系卡牌命名

**[下载 Windows 独立试玩包（2026-10-29 火系命名版）](https://github.com/qqzj1071/Magicians-/raw/refs/heads/main/releases/windows/Magicians-Fire-Naming-20261029.zip)** · [SHA-256 校验](releases/windows/Magicians-Fire-Naming-20261029.zip.sha256)

完整解压后双击包内 `Magicians.exe`，无需安装 Godot、Python 或 .NET。分享时请发送整个压缩包，不能只发送快捷方式或 EXE。

本次更新涵盖全部 38 张火系卡牌，30 张采用新显示名，卡牌数值、效果、构筑规则和 AI 模型保持现行版本。38 条小字完整保存在[火系定稿](docs/lore/fire-all-final.txt)与 `Data/Creative/fire-flavor-texts.zh-CN.json`，局内暂不显示；[新旧卡名对照](docs/lore/fire-card-names.txt)随独立包一并提供。包内冻结版卡牌 DOCX 仍使用原名，请结合对照表查阅。

Windows 试玩版采用正式的免安装 ZIP：完整解压后双击 `Magicians.exe`，无需安装 Godot、.NET SDK 或 Python，也无需联网。请保留 EXE、PCK、data_Magicians!_windows_x86_64 与 runtime-data 的相对位置。包内提供卡牌 DOCX 与可选的桌面快捷方式脚本。发布流程和完整性保护限制见 [Windows 免安装发布](docs/client/portable-release.md)。

以下安装开发环境的步骤仅适用于源码协作。发布包仅在明确要求时构建，不随每次代码提交自动更新。

## 下载与试玩

### Windows 免安装试玩（推荐）

支持 **Windows 10/11 64 位**。当前独立包为 **2026-10-29 火系命名更新版**，沿用现行 v1.0 规则，下载约 **85 MB**。

1. 点击 **[下载完整独立包](https://github.com/qqzj1071/Magicians-/raw/refs/heads/main/releases/windows/Magicians-Fire-Naming-20261029.zip)**，得到 `Magicians-Fire-Naming-20261029.zip`。
2. 右键压缩包，选择“全部解压”，将整个文件夹解压出来；不要在压缩包窗口内直接运行。
3. 打开解压后的 `Magicians-Fire-Naming-20261029` 文件夹，双击 **`Magicians.exe`**。
4. 在主菜单点击 **“开始单人赛事”**。首次进入赛事时请等待内置 AI 加载。玩家淘汰后可以查看逐轮复盘，或让 AI 自动完成剩余赛事直到冠军产生。

**无需另装 Godot、Python、.NET SDK，也无需联网游玩。** 所需运行环境已随包提供。请保留 `Magicians.exe`、`Magicians.pck`、`data_Magicians!_windows_x86_64`、`runtime-data` 及其他随包文件的相对位置，不要单独移动 EXE。

### 分享、快捷方式与随包资料

- 分享给别人时，发送**整个 ZIP**，让对方完整解压后启动；只发送 EXE 或桌面快捷方式无法运行。
- 想创建桌面入口，可以双击包内 `Create-Desktop-Shortcut.vbs`。移动游戏文件夹后，需要重新创建快捷方式。
- `README.txt` 是包内使用说明；`FIRE-CARD-NAMES.txt` 是新旧卡名对照；`FIRE-FLAVOR-TEXTS.txt` 保留全部 38 条火系小字，小字暂不在局内显示。
- 卡牌 DOCX 保留冻结版规则及原名，查询新卡名时请配合对照表。
- 若提示文件缺失或完整性校验失败，请重新完整解压原压缩包，避免混用不同版本文件。需要核对下载文件时，可使用 [SHA-256 校验值](releases/windows/Magicians-Fire-Naming-20261029.zip.sha256)。

### 源码协作与本地调试

仅试玩请使用上面的独立包。仓库 **Code → Download ZIP** 会下载整个源码仓库；直接下载独立包更方便。开发和修改客户端仍需准备 Godot 4.7.2 .NET 等开发环境。协作者请参考[上手与协作说明](CONTRIBUTING.md)；独立包构建与验收见 [Windows 免安装发布](docs/client/portable-release.md)。

当前项目版本为 **v1.1.2**；卡牌与牌组构筑规则仍沿用冻结的 **v1.0**。请从[文档入口](docs/README.md)开始。

唯一卡牌数据：releases/v1.0/cards.json；唯一构筑规则为[构筑v1.0](releases/deckbuilding-v1.0/README.md)。旧规则与实验已压缩标记过时，默认不读取。当前阶段为固定规则下的四人赛事AI学习。

完整四人赛事AI已完成[十轮学习与独立终测](docs/ai/tournament-v1-report.md)。固定标准牌组历史六轮先验独立保留；当前标准牌组由decks/active.json指定。卡牌与构筑规则未因训练修改。

共创者请从[上手与协作说明](CONTRIBUTING.md)开始。当前[世界观与美术方向](docs/lore/README.md)为“魔法集会与魔法师大赛”；项目包含设计资料、模拟与AI研究工具，已包含可运行的单人客户端，联机功能仍待继续开发。

