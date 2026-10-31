# Magicians! v1.2

多人战斗与牌组构筑独立游戏。Windows v1.2 客户端已验收，现为唯一正式客户端。

当前源码已迁移为完整 C# 工具链，游戏、六风格 AI、训练、审计、测试与打包均无需 Python。支持完整四人单人赛事、手动构筑与战斗、AI托管、赛事排名、当前轮复盘和分辨率设置。默认1920×1080。实时联机尚未接入。

用 Godot .NET 打开 project.godot；开发检查运行 `dotnet run --project tools/Magicians.Tooling -- test`。[下载最新 Windows 免安装包](https://github.com/qqzj1071/Magicians-/releases/download/v1.2-csharp-canonical-20261031/Magicians-v1.2-CSharp-Windows-x64.zip)，完整解压后运行 Magicians.exe。迁移依据及验证见[迁移记录](docs/csharp-migration.md)。

- [当前发行与校验](releases/client-v1.2.json)
- [开发、构建和验证](docs/development.md)
- [卡牌与规则](docs/cards-v1.2/README.md) · [全部卡牌](docs/cards-v1.2/catalogue.md)
- [构筑规则](releases/deckbuilding-v1.2/README.md)
- [世界观与创作](docs/lore/README.md)
- [项目约束](AGENTS.md)

卡牌共183张、库存677份。代码、卡表、UI、检索与选择统一采用定稿卡名；五系25张传奇与专精卡显示创作文案。所有火系卡（含专精、传奇）统一计作火系附魔牌。

旧版本和历史研究报告已移出活动项目并压缩归档。GitHub 的旧提交仅供追溯，不是当前开发依据。
