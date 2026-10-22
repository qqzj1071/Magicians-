# Magicians! 当前工作约束

- 当前卡牌唯一版本为v1.0。先读docs/README.md，再读releases/v1.0/cards.json；docs/cards/*.md为生成视图，不是另一份版本。
- 默认不解压、不检索archives/pre-v1.0.zip，不引用旧版卡表、胜率、克制标签。用户明确要求追溯时才能恢复指定文件。
- 本轮卡牌已封版。后续构筑任务只调整流程/牌组，不隐含授权改卡牌；新版本调整须另行记录。
- 数值规范见docs/combat/numeric-standards.md：机制科学计数法尾数半单位；普通未选专精效果严格为已选专精一半；固定价值=攻+1.5防，同稀有度差距≤20%。
- decks/active.json指向当前学习后的15套固定牌组；decks/decks.json保留封版参考与回归。构筑讨论起点见docs/deckbuilding/process-draft.md，不把研究配额当成正式局内规则。
- 战斗运行器在tools/round_robin，只验证单主系加通用的双人模拟；混系传奇机制和多人赛事尚未完整实现。当前AI经过6轮学习、120组各200场独立测试，入口docs/ai/training-v1/report.md；仍有36组严重克制，不得宣称全部解决。
- 共性、路线与个性参数在tools/round_robin/policies.json；原始研究记录在research/ai-v1.0-learning，默认从文档总结读取。逐张抓牌模型没有验证出优于纯启发式的额外收益，不能当成成熟抓牌器。
- 改卡表或构筑后必须重新校准所涉对局；不得混用旧结论制造达标。运行python tools/round_robin/verify_v1.py检查封版与回归。
