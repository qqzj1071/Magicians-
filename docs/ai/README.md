# 构筑与战斗AI · 当前入口

卡牌v1.0与[构筑v1.0](../../releases/deckbuilding-v1.0/README.md)冻结；AI检查点独立演进，不能回写游戏规则。

客户端已通过 `tools/client_ai/inference_worker.py` 接入本页指针指定的检查点，校验 `model_sha256`，直接复用研究版 `Learner`、构筑特征/评分、刷新估值、战斗阶段规划与检索候选评分。仅执行推理，不学习、不修改权重，不改冻结的engine.py、planner.py或policies.json。战斗规则仍由C#引擎权威执行；Python中的条件预演是决策建议，不能作为客户端实际结算或必杀保证。

`Scripts/Core/AI/AiObservations.cs` 是唯一的新AI观察边界：自身已知牌组组成、当前手牌和弃牌区、可见战斗数值、当前构筑候选与自身经济状态，以及全场公开的专精/路线/赛事血量和下一对手。禁止传递摸牌顺序、随机状态、对手私有牌组/手牌/候选/经济状态、隐藏库存、未来候选及对手待提交动作。检索候选在确定要打出哪张检索卡之后单独发送，不能提前看所有检索结果再选牌。

每名参与者使用独立的常驻Python进程，进程会绑定参与者ID，避免不同AI共享推理缓存中的私有观察。Godot主线程只投递任务与提交完成的决策；过期状态版本的决策被丢弃，实际费用、库存、行动合法性仍由权威命令校验。模型不可用或推理失败会明确暂停并显示原因，不静默回退为旧简化策略。

本机Python路径位于 `tools/client_ai/runtime.json`，可用 `MAGICIANS_PYTHON` 环境变量覆盖。每次赛事独立管理并释放推理进程，无网络依赖。程序使用当前已安装的Python运行时，不额外下载安装。

运行 `tools/run_client_regressions.ps1` 可执行构建、完整多轮回放、隐私边界变异测试和异步客户端流程测试。结果保存在工作区 `runtime/regressions/trained-ai/`：每个种子两份run JSON、逐轮/逐战事件摘要、观察哈希、决策理由、模型与源文件哈希、最终状态哈希及总事件摘要哈希。`summary.json` 仅在重复回放的两种哈希一致后生成。固定基线位于 `Data/Regression/trained-ai-baselines.json`，模型或行为变化须明确审查并更新，测试不会自动接受新的基线。

- [十轮四人赛事学习及独立终测](tournament-v1-report.md)
- [训练、回退与防过拟合方法](tournament-v1-method.md)
- [真实抓牌、存费和出牌理由示例](tournament-v1-decisions.md)
- [当前研究检查点指针](current-tournament.json)
- [卡牌平衡测试计分约定](card-balance-testing.md)

研究候选可用tools/round_robin/tournament_inference.load_release读取research/tournament-v1-training01。实际推荐模型以current-tournament.json中的model与哈希为准；混合赛事若明确退步，保留冻结前AI作为默认。整体是否更强以独立终测与区间为准，不能用自弈胜率、训练次数或Dice代替战力。

后续训练必须换新的研究名称与种子空间；工具默认接当前推荐检查点继续学习，也可显式指定checkpoint。不覆盖本次结果，不重用终测种子调参。

冻结前策略仍保留于releases/deckbuilding-v1.0/initial-ai.json，旧构筑规则与实验已压缩且过时，默认禁止解压。固定15套标准牌组的历史战斗先验仍见[报告](training-v1/report.md)、[共性](training-v1/common.md)与[历史构筑课程](training-v1/construction.md)，不把它们作为现行赛事规则。
