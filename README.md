# Magicians! v1.2

多人战斗与牌组构筑独立游戏。Windows v1.2 客户端已验收，现为唯一正式客户端。

解压发行 ZIP 后运行 `Magicians.exe`。内置 Python 和六风格 AI，无需安装开发环境；支持完整四人单人赛事、手动构筑与战斗、AI托管、赛事排名、当前轮复盘和分辨率设置。默认1920×1080。实时联机尚未接入。

- [当前发行与校验](releases/client-v1.2.json)
- [开发、构建和验证](docs/development.md)
- [卡牌与规则](docs/cards-v1.2/README.md) · [全部卡牌](docs/cards-v1.2/catalogue.md)
- [构筑规则](releases/deckbuilding-v1.2/README.md)
- [世界观与创作](docs/lore/README.md)
- [项目约束](AGENTS.md)

卡牌共183张、库存677份。运行卡名保留为稳定规则 ID，五系定稿显示名已接入客户端；显示资料位于 Data/Presentation/card-display.json，由 tools/build_v12_presentation.py 从五系 *-name-map.json 生成，新增或改名后先运行生成脚本。小字保留 display_in_match=false，暂不在局内显示。所有火系卡（含专精、传奇）统一计作火系附魔牌。

旧版本和历史研究报告已移出活动项目并压缩归档。GitHub 的旧提交仅供追溯，不是当前开发依据。
