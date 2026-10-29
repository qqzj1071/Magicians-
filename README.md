# Magicians!

## 合作者卡牌查阅入口（2026-10-29）

当前 v1.2 设计包含185张卡牌、693份流通库存。请从 [v1.2 卡牌说明](docs/cards-v1.2/README.md) 和 [全部卡牌总表](docs/cards-v1.2/catalogue.md) 开始。

- [火系选名与机制](docs/cards-v1.2/fire.md)：31张逐卡选名、旧名对照与理由；传奇及专精含对应风味文案。选名尚未同步为运行数据名称。
- [水系](docs/cards-v1.2/water.md) · [土系](docs/cards-v1.2/earth.md) · [风系](docs/cards-v1.2/wind.md) · [毒系](docs/cards-v1.2/poison.md) · [通用](docs/cards-v1.2/generic.md)
- [命名与文案指南](docs/lore/naming-guide.md) · [世界观](docs/lore/README.md) · [构筑 v1.2](releases/deckbuilding-v1.2/README.md)

客户端规则基线为冻结的 [v1.1](releases/v1.1/README.md)；v1.2 由[独立模拟器](tools/sim_v12/README.md)执行。下方 v1.0 介绍与研究报告保留历史背景，当前版本以本入口及[文档说明](docs/README.md)为准。


## 下载与试玩

当前仓库包含可运行的 Godot 4.7.2 .NET 单人客户端。Windows 玩家可以：

1. 安装 Godot 4.7.2 .NET/Mono 版本，并准备 .NET 8 SDK。
2. 克隆仓库：

   ```powershell
   git clone https://github.com/qqzj1071/Magicians-.git
   cd Magicians-
   ```

3. 用 Godot .NET 打开项目根目录中的 `project.godot`，点击运行。
4. 在主菜单点击“开始单人赛事”。玩家淘汰后可以查看逐轮复盘，或让 AI 自动完成剩余赛事直到冠军产生。

客户端的固定规则数据、卡面展示档案、占位素材和 C# 源码均已包含在仓库中。运行前不需要 Python；Python 运行时只用于训练 AI 的客户端推理适配，项目会从 `tools/client_ai/runtime.json` 读取配置。

开发者可以在项目根目录运行：

```powershell
dotnet build Magicians!.csproj --no-restore
powershell -ExecutionPolicy Bypass -File tools/run_client_regressions.ps1
```

完整客户端回归会检查卡牌执行、构筑库存、战斗公式、AI 隐私、主菜单、淘汰后观战和固定种子赛事回放。

当前卡牌版本与牌组构筑版本均为 **v1.0**。请从[文档入口](docs/README.md)开始。

唯一卡牌数据：releases/v1.0/cards.json；唯一构筑规则为[构筑v1.0](releases/deckbuilding-v1.0/README.md)。旧规则与实验已压缩标记过时，默认不读取。当前阶段为固定规则下的四人赛事AI学习。

完整四人赛事AI已完成[十轮学习与独立终测](docs/ai/tournament-v1-report.md)。固定标准牌组历史六轮先验独立保留；当前标准牌组由decks/active.json指定。卡牌与构筑规则未因训练修改。

共创者请从[上手与协作说明](CONTRIBUTING.md)开始。当前[世界观与美术方向](docs/lore/README.md)为“魔法集会与魔法师大赛”；项目包含设计资料、模拟与AI研究工具，联机和可玩客户端仍待继续开发。
