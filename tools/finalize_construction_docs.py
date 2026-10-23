"""Replace stacked historical entry points by one current release pointer."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FILES={
'docs/README.md':'''# Magicians! · 当前版本入口

卡牌v1.0与牌组构筑v1.0均已冻结，AI继续学习；规则变更须另开版本。

1. [构筑v1.0规则与数据](../releases/deckbuilding-v1.0/README.md)：共享池、概率、研习、公开信息、四人淘汰与六阶段扣血。
2. [卡牌v1.0](cards/README.md)：唯一数据releases/v1.0/cards.json，共253张。
3. [构筑与战斗AI](ai/README.md)：学习状态、独立验证与检查点。
4. [15套标准牌组](../decks/README.md)。
5. [伤害](combat/damage-model.md)、[结算](combat/resolution-order.md)、[数值规范](combat/numeric-standards.md)。

旧构筑规则和实验已压缩标记过时，默认不解压、不引用为当前规则，见[归档说明](../archives/README.md)。研究运行器支持四人淘汰赛事，不等于联机和客户端已完整实现。
''',
'AGENTS.md':'''# Magicians! 当前约束

- 先读docs/README.md。唯一卡牌releases/v1.0/cards.json（253张）；唯一现行构筑规则releases/deckbuilding-v1.0/README.md及manifest校验数据。用户已接受冻结，AI训练不得改变卡牌、概率、份数、经济、保底、扣血。
- 旧规则、报告、shared-draft原始实验压缩为archives/obsolete-deckbuilding-pre-v1.0.zip，已过时。默认不解压不检索不引用为当前规则；archives/pre-v1.0同理。只在用户明确要求历史追溯时恢复指定文件到独立目录，不能覆盖现行数据。
- 非传奇按普通/稀有/史诗×附魔/通用六类等份数6/8、4/6、3/4，共1060份；同类不能逐卡偏置。通用传奇2份、路线/叠层1份。玩家同名唯一，初始攻防各2例外。实体库存不能超发，删除/替换/淘汰下轮回池。
- 专精3同系立即赠卡并提升已有附魔收益。专精前同面同系最多1张，专精后本系65%软目标，无新异种。研习growth-v3兼容实现，继承≤2，刷新每轮1次1点。8/10/12首面前三传奇尽量2路线；刷新面最低稀有度启用位补1传奇。
- 专精和选择/替换路线即时全场播报。构筑AI只看自己的牌组、已展示候选、下一对手及公开信息，不看对手私有牌组、未来候选、随机数。唯一路线被抢及时重评目标。
- 四人初始100赛事血，构筑前公布配对，一轮一战，能避免时不连遇。三人用淘汰快照幽灵。3/6/9…连胜败下轮+1点；双死中断且各扣基础。淘汰停购下轮回池，直到≤1活人，最后同时全灭沿用并列冠军，不截断或伪造唯一冠军。
- 扣血m+floor(ln(max(x,1))*n)，1—4=(2,.8)、5—8=(4,1.8)、9—12=(7,2)、13—14=(9,3.2)、15—16=(10,4.5)、17以后=(11,6)恒定。当前已接受，不因历史节奏目标未达自行调参。
- decks/active.json指向15套现行标准牌组；Dice不是战力。AI学习分训练/验证/终测，双方学习，完整赛事，固定规则，有回退和关键决策理由。不能用自弈50%胜率或训练场数证明提升；不能承诺所有决策最优。
- 数值规范docs/combat/numeric-standards.md。冻结engine.py/planner.py/policies.json不擅改；适配层独立验证。完成训练需verify_v1.py及赛事库存/公开信息边界回放。最新AI入口docs/ai/README.md。
''',
'docs/ai/README.md':'''# 构筑与战斗AI

游戏规则已冻结为[构筑v1.0](../../releases/deckbuilding-v1.0/README.md)，卡牌保持v1.0。当前正在进行十轮完整四人赛事训练，入口tools/round_robin/train_tournament_v1.py；运行数据保存在research/tournament-v1-training01，完成后以独立终测报告为准。冻结起点为releases/deckbuilding-v1.0/initial-ai.json。

15套标准牌组是构筑参考。学习需同时考虑赛事存活、即时战力、运转、专精门槛、公开对手和未来收益，不把相似度当战力。新参数经过独立种子验证，未通过则回退；终测不参与调参。

固定套牌历史战斗基础仍见[报告](training-v1/report.md)、[共性](training-v1/common.md)与[构筑方法](training-v1/construction.md)。这些是历史先验，不代表当前四人构筑强度。旧构筑实验已经压缩标记过时，禁止默认读取。研究AI不能被描述为已达到最优。
'''}
for relative,text in FILES.items():(ROOT/relative).write_text(text,encoding='utf-8')
p=ROOT/'archives/README.md'
old=p.read_text(encoding='utf-8')
p.write_text('''# 构筑旧规则：已过时

obsolete-deckbuilding-pre-v1.0.zip保存构筑v1.0冻结前规则、候选、报告及shared-draft原始实验。包内manifest保留原路径与SHA-256；逐文件读取验证后才移除工作副本，校验记录为obsolete-deckbuilding-pre-v1.0-verification.json。默认不解压、不检索、不作为当前规则；只在用户明确要求追溯时恢复指定文件到独立目录，禁止覆盖现行数据。

当前唯一构筑规则：[构筑v1.0](../releases/deckbuilding-v1.0/README.md)。卡牌版本独立保持releases/v1.0/cards.json。

'''+old,encoding='utf-8')
