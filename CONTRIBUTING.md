# 共创者上手说明

## 当前项目状态

这是多人战斗与卡牌构筑游戏 Magicians! 的开发仓库，包含 Godot 项目配置、游戏设计文档、冻结卡牌与构筑数据、Python 战斗模拟和 AI 研究工具。研究运行器可以执行四人赛事，但不代表联机和可玩客户端已经完成。

世界观以“魔法集会与魔法师大赛”为核心；卡牌与构筑均为 v1.0。请先读 [项目约束](AGENTS.md) 和 [文档入口](docs/README.md)。

## 从哪里继续

| 工作方向 | 入口 |
|---|---|
| 世界观、人物、美术、命名 | [世界观总纲](docs/lore/README.md) |
| 卡牌数据与效果 | [卡牌入口](docs/cards/README.md)、`releases/v1.0/cards.json` |
| 当前构筑、库存、经济和赛事 | [构筑 v1.0](releases/deckbuilding-v1.0/README.md) |
| 战斗时序、伤害、数值 | [文档入口](docs/README.md)中的战斗文档 |
| AI 研究与当前检查点 | [AI 入口](docs/ai/README.md)、[工具说明](tools/round_robin/README.md) |

## 本地准备与核验

克隆仓库后，在仓库根目录运行。Python 工具本次使用 Python 3.12 验证；以下检查使用标准库，不需要安装额外依赖。

```powershell
python tools/round_robin/verify_v1.py
python tools/round_robin/verify_construction_v1.py
python tools/round_robin/test_strategic_tournament_ai.py
```

Godot 配置当前标记为 4.7、Forward Plus，包含 C# 程序集设置。需要编辑客户端时从 `project.godot` 打开，依当地可用的匹配编辑器环境继续开发；这些配置不是完整客户端已构建通过的证明。

## 协作约定

- 从最新 `main` 新建工作分支，按主题提交，通过 Pull Request 汇总改动。
- 卡牌与构筑数据已冻结；规则调整需讨论并另开版本，不能把 AI 训练结果直接写回规则。
- 世界观地名、人物细节、奖励和精确画风仍是草案；逐卡改名与效果改写尚待开展。
- 新 AI 实验使用独立研究名称与种子空间，不覆盖已有研究，也不重用终测数据调参。
- `archives/` 中旧规则与实验仅供溯源，默认不解压、不当作当前规则。世界观旧稿见 `docs/lore/archive/`。
- 不提交密码、令牌、环境文件、Godot 缓存或 Python 缓存。生成素材前明确用途、尺寸、透明背景和版本。
