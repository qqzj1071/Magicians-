# v1.2独立构筑与战斗模拟器

230张现行卡牌，6种初始专用牌不入池，共870份流通库存。初始8张为攻击强化×2、防御强化×2、护盾、检索附魔、短促、重洗。初始实例单独创建，删除或淘汰不会向共享池凭空增发基础牌。

本目录不导入round_robin的战斗引擎、卡牌效果、AI权重或默认牌组指针，不依赖Godot。卡表由docs/cards-v1.2六份当前卡表读取；机器快照随每次运行导出。池分配保留原有联合最小费用流算法，并增加初始牌排除及10/12轮已有路线者两面合计至多新展示1路线的约束。概率、份数、扣血等配置独立保存在rules目录。

在项目根目录运行：

```powershell
& 'C:\Users\33763\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tools.sim_v12.test_current
& 'C:\Users\33763\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m tools.sim_v12.quick_test --games 500 --seed 281200 --out 'research/v1.2-quick-new'
```

输出目录必须不存在，防止覆盖先前实验。快速测试默认500局、每名玩家独立随机AI风格，排名分+3/+1/−1/−3。每局保存完整构筑账本、战斗种子/出牌统计和排名；逐局失败立即报错，不补造结果。输入源码、配置与卡文哈希在运行末尾复核。statistics.json提供5元素、15路线、230张牌的携带、曝光、胜率、得分、夺冠及风格分项，report.md与cards.md便于阅读。`--workers`控制进程数。旧`__main__`入口仍供小样本诊断，正式统计使用quick_test。

主要模块：

- catalog.py：230张当前卡牌、能力牌身份、初始牌及共享库存。
- model.py：稳定实例、牌区、首次记录、阶段折扣、到期状态。
- effects.py：230张显式效果注册；缺失效果立即报错，无旧版回退。
- engine.py：独立战斗数值、牌区操作、同步发射、毒与到期。
- locked.py：默认正式模式。先独立运转并锁定实例/选择/费用，再按位次提交真实战斗效果；行为边界使用已提交结果继续，真实事件触发土系插入斩杀，死亡/复活截断尾段。
- pool.py、tournament.py：联合候选、经济、专精/路线、替换/删牌、有限库存、配对、幽灵、赛事扣血及排名。
- policy.py：15条路线的合法目标牌组与新启发式AI；选牌只使用自己的手牌或明确展示的候选，以及公开对手状态。未训练，不承诺最优。

基础战斗数值为1000生命、100攻击、40防御，每100行动值基础抽5张/获得3费，首发100，基础间隔50、最终向下取整、下限1。疲劳沿用1500起每抽牌阶段出牌后向上取整。生命支付、普通伤害、临时盾、毒层等规则分别处理；效果中的“永久”均只持续本场。

规则详见docs/cards-v1.2/snapshot-contract.md。规划不造成伤害或命中反馈，不提前激活真实能力；只保证存活前缀的手牌/费用运转，治疗和潮汐等战斗资源按真实状态计算。普通飞弹保持同步批次，土系每次敌方生命/己方盾变化后的主动斩杀可插入卡内行为之间。旧live和private_positions_experimental保留为历史诊断，不作为新规则样本。

模拟器使用稳定随机流和有理数。卡牌序列或调度不终止时会报错并停止该次实验，保留已完成记录，不悄悄限制卡牌触发次数、跳过效果或制造胜者。完整检查和剩余限制见research/v1.2-implementation-20261028/report.md。

当前训练入口：`python -m tools.sim_v12.train --out research/v1.2-training-1000-20261028`。10批×100局，每批60训练、20验证选检查点、20封存对照；构筑/战斗/选择共享可学习机制权重，旧策略仅作明确对照，均使用230张及严格快照。

已完成批次见research/v1.2-training-1000-final-20261028/report.md。候选accepted-08保存在final-policy.json；封存对照成绩下降，未提升为默认。rules/ai-policy.json当前为deployment-fallback-legacy，保留严格快照及共同经济循环改选/退出。新机制模型可通过simulate的policy_by_seat显式传入检查点，不读取v1.1策略。旧训练目录已标诊断作废，不混入正式1000局。
