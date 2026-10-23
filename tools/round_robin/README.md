# 卡牌v1.0战斗工具

当前四人构筑/淘汰训练入口为`train_tournament_v1.py`，默认十轮，规则只读`releases/deckbuilding-v1.0`。检查规则用`verify_construction_v1.py`，检查策略与信息边界用`test_strategic_tournament_ai.py`，训练报告入口`docs/ai/README.md`。本目录旧版calibrate/optimize/report及早期shared-draft训练脚本仅为历史工具，不是现行规则入口，不要用它们覆盖冻结数据或自动解压旧实验。

唯一数据为releases/v1.0/cards.json；decks/decks.json仅15套参考列表。运行 python tools/round_robin/verify_v1.py 检查253张面板、253项出牌事务、15组确定性战斗、225项策略绑定和数值规范。

engine.py为事务执行器，planner.py为启发式贪心出牌，controller.py调用现有策略。历史数值修改与训练脚本已归档，避免意外覆盖封版卡牌。改构筑后旧策略哈希会失效，须重新校准。

运行 python tools/render_cards.py 从冻结数据生成卡面。下一阶段构筑任务不自动授权更改冻结卡牌。

当前AI入口：docs/ai/training-v1/report.md。controller.policy_for支持common、route、matchup三个层级；默认matchup，并校验当前牌组、卡表及出牌器的哈希。改牌组后旧胜率和参数不能自动作为已验证结论。

构筑候选排序调用draft_learning.choose_offer；其学习修正层仍属实验，未在独立抓牌测试中超过纯启发式。当前推荐流程是先验提出候选、贪心仿真筛选、全对手验证。

新实验先设置独立的MAGICIANS_AI_RUN名称；目录与种子命名空间会随名称更换，禁止覆盖已完成实验或复用最终测试种子做训练。train_v1.py执行六轮，--resume仅恢复未完成实验；finish_learning.py完成独立检查与发布。卡牌和v1.0发布包始终只读。
