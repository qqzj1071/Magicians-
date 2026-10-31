# C# 全量迁移记录

2026-10-31：已完成当前项目的C#迁移与运行代码替换。游戏、AI、训练、统计、资料生成、审计、校验和打包均不再调用Python。

## 实现与卡名

采用[合作者的C#重构](https://github.com/sjtu-Mutsumi/Magicians-drifts-)作为实现基础，按当前工作区的最新定稿卡名适配，而非整库覆盖。审查副本的native-source-manifest SHA256为 `93c91be1626d07e54d6027acf64dd134717d03edc63c870fc1917f59322bdd31`。

- Scripts/Native：纯C#规则内核，包含精确有理数、Python兼容MT19937与洗牌、状态复制、Battle/LockedBattle/StrictBattle结算、构筑、六风格AI和四人赛事。
- Scripts/Application：调用NativeBridge与NativeMatchSession，取代Python子进程，保留原异步交互、revision检查和私有信息边界。
- tools/Magicians.Tooling：独立.NET 8命令行项目，与Godot共享Native源码；Godot项目排除tools源码的重复编译。
- 183个运行标识、卡表、界面与检索统一采用当前定稿卡名。103处旧身份差异按完整字符串及内嵌JSON结构适配，不引入别名映射，不使用会误伤其他完整卡名的子串替换。
- 卡名参与战斗种子哈希，故重新采集当前Python参考，未将旧名称的随机回放冒充当前行为。
- 保留原Presentation、Core、Scenes、卡牌文案与展示方式。NativeBridge补齐enchantment_applied，使现有卡面首次附魔状态及选择候选继续正确显示。

迁移前快照对比：原Presentation、Core、Scenes、Data、规则JSON、六模型及其清单、卡表、旧冻结清单与战斗规则共49个文件逐字节不变。新增的card-display.json仅导出当前名称和词条；183个导出名与运行ID完全一致，不依赖旧name-map.json。

## 来源与冻结

迁移前71个Python源码的精确工作区内容保存在 `releases/v1.2/python-migration-baseline.zip`。retired-python-manifest逐文件记录SHA，并校验归档的完整条目集合和内容。没有把本地未提交修改归因于旧Git提交。

旧freeze-manifest、卡表、规则和模型保持原有校验。native-source-manifest保护当前C#源码、资料、模型及文件集合；新增、缺失或修改均拒绝。归档仅为溯源证据，不执行、不随游戏打包。活动Python文件和编译缓存已移除。

测试证据的来源分别记录在Testing/Fixtures/manifest.json和Training/Fixtures/parity.json：

- 366个卡牌场景、15场路线战斗、7场赛事和27项协议响应，从替换前当前Python实现独立采集。
- 3场训练赛事由当前Python训练worker独立采集；其余统计与固定提案沿用合作者的原始证据并按完整身份适配。
- 1214个业务操作从原证据翻译卡名，保留原随机状态、操作前状态与结果；原始文件哈希保留在fixture清单中。
- 测试运行只读取固定JSON/GZip数据，不需要Python。

## 已完成验证

| 检查 | 结果 |
| --- | --- |
| .NET/Godot构建 | 通过，零警告、零错误 |
| 精确数值、随机序列、克隆 | 通过 |
| 机制/静态/策略/损坏守卫 | 551 / 532 / 55 / 12项通过 |
| 当前卡牌/战斗/赛事回放 | 366 / 15 / 7项通过 |
| 原业务操作、协议 | 1214次操作、27项响应通过，含隐私和非法输入 |
| 训练算法与统计对照 | 41647项通过 |
| 十种训练模式小预算流程 | 358局，零跳过，输入哈希复核通过，未部署模型 |
| Godot七项无头场景 | 全部通过；手动赛事609步、四人排名完成 |
| 图形过渡 | D3D12实测买牌/出牌过渡通过 |
| 文案图形展示 | 五系25张传奇/专精通过，并检查生成画面 |
| 资料生成 | 定稿展示、卡牌总表、跨层审计的--check通过 |
| C#源码与冻结完整性 | 通过，退休源码逐条归档校验 |
| Windows独立包 | 禁用Python烟测及全部文件完整性检查通过，包内无Python |

本地验证包：`D:/Magicians!/_installers/Magicians-v1.2-CSharp-Windows-x64/Magicians.exe`。当前发行清单已更新，完整验证摘要见validation-20261031.json。回归入口和桌面快捷方式也统一改为C#命令，已移除剩余PowerShell源码。构建和使用方式见development.md。

主要验证证据已整理到外层runtime/validation-20261031，包括客户端回归、图形截图、358局训练摘要、发行包审计和cleanup-manifest.json。旧混合版程序、临时源码、过渡备份与嵌入式Python环境已删除；当前源码由Git main和源码ZIP保存，规则来源由只读冻结证据保存。

以上为有限回归和小预算训练，不代表穷尽所有组合或完成原大规模训练；本次未调整规则、数值或模型，也未接入实时联机。
