# 构筑与战斗AI · 当前入口

卡牌v1.0与[构筑v1.0](../../releases/deckbuilding-v1.0/README.md)冻结；AI检查点独立演进，不能回写游戏规则。

- [十轮四人赛事学习及独立终测](tournament-v1-report.md)
- [训练、回退与防过拟合方法](tournament-v1-method.md)
- [真实抓牌、存费和出牌理由示例](tournament-v1-decisions.md)
- [当前研究检查点指针](current-tournament.json)

研究候选可用tools/round_robin/tournament_inference.load_release读取research/tournament-v1-training01。实际推荐模型以current-tournament.json中的model与哈希为准；混合赛事若明确退步，保留冻结前AI作为默认。整体是否更强以独立终测与区间为准，不能用自弈胜率、训练次数或Dice代替战力。

后续训练必须换新的研究名称与种子空间；工具默认接当前推荐检查点继续学习，也可显式指定checkpoint。不覆盖本次结果，不重用终测种子调参。

冻结前策略仍保留于releases/deckbuilding-v1.0/initial-ai.json，旧构筑规则与实验已压缩且过时，默认禁止解压。固定15套标准牌组的历史战斗先验仍见[报告](training-v1/report.md)、[共性](training-v1/common.md)与[历史构筑课程](training-v1/construction.md)，不把它们作为现行赛事规则。
