# Magicians! · 当前版本入口

卡牌运行基线v1.1已冻结；v1.2已接入[独立Python模拟器](../tools/sim_v12/README.md)，不改变v1.1客户端。当前构筑经济采用[v1.2调整](../releases/deckbuilding-v1.2/README.md)，其余构筑规则沿用v1.0及已确认修订。

现行v1.2为[192张卡牌总表](cards-v1.2/catalogue.md)、718份库存；规则见[跨层读取规范](cards-v1.2/snapshot-contract.md)，由独立 strict 内核执行，v1.1客户端保持冻结。双方读位次前快照，本位新防护从下一位起保护对方效果。

最新[循环附魔层检查](../research/v1.2-repeat-enchantment-review-20261029/report.md)：已删除穿甲；潮汐恩泽、大地之盾、山岳壁垒列为待删候选，尚未移出。下方2000局报告使用删穿甲前的193张卡表。

最新[20轮2000局薄牌组训练报告](../research/v1.2-thin-deck-2000-20261029/report.md)：58,641场战斗、零跳过；24项回归通过，37张删牌及专属状态清理完成。薄模型对同战斗原构筑有正向终测结果，但对旧默认的均分差区间仍跨0，候选保留、默认未替换。逐卡携带与使用率、路线及问题表均在报告中。

此前230张版本的[v1.2运转AI训练报告](../research/v1.2-training-1000-final-20261028/report.md)：10批×100局、28,957场战斗；候选运转用量提高但封存战绩下降，默认回退旧启发式。完整路线及逐卡统计见报告。

此前239张版本的[v1.2快速500局报告](../research/v1.2-quick-500-final-20261028/report.md)：14,533场战斗、逐卡携带/得分/夺冠统计；18种通用高阶牌存在AI零采用盲区，不能直接据零携带删除，也不能把旧规则结果当作新规则训练提升。

1. [构筑v1.0规则与数据](../releases/deckbuilding-v1.0/README.md)：共享池、概率、研习、公开信息、四人淘汰与六阶段扣血。
2. [卡牌v1.1](cards-v1.1/README.md)：唯一现行数据releases/v1.1/cards.json，共252张。
3. [构筑与战斗AI](ai/README.md)：学习状态、独立验证与检查点。
4. [15套标准牌组](../decks/README.md)。
5. [伤害](combat/damage-model.md)、[结算](combat/resolution-order.md)、[数值规范](combat/numeric-standards.md)。
6. [客户端构筑规则审计与显示设置](client/draft-offer-audit.md)：全量候选分配、保底、回归入口与分辨率设置。

旧构筑规则和实验已压缩标记过时，默认不解压、不引用为当前规则，见[归档说明](../archives/README.md)。研究运行器支持四人淘汰赛事，不等于联机和客户端已完整实现。

## 世界观与美术创作

[世界观入口](lore/README.md)：lore v0.2，以魔法集会与魔法师大赛为核心，包含世界、人物、美术方向和命名文案规范。[产品概念](game-concept.md)供首次了解项目的合作者阅读。创作资料不作为规则或功能实现依据。
