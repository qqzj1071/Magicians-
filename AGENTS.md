# Magicians! v1.2 — 当前项目约束

v1.2 已于 2026-10-30 验收，完全替代 v1.1。主入口 Scenes/Boot/Boot.tscn → MainMenu → Scenes/V12/SinglePlayer.tscn。不存在旧客户端回退入口。

- 权威规则：Scripts/Native，183张卡牌、677份库存；NativeMatchSession 在 C# 后台线程暂停/恢复四人赛事。Scripts/Application 连接现有 Godot 界面，禁止恢复 Python 子进程或另一套规则。
- 卡牌：releases/v1.2/cards.json 与 docs/cards-v1.2。全项目统一使用定稿卡名作为运行标识，不保留别名。Data/Presentation/card-flavor.json 保存五系25条传奇与专精文案，由卡面及提示展示。全部火系卡（含专精/传奇）属于火系附魔牌；ability 与打出后移出规则独立。
- AI：releases/ai-v1.2-six-styles-20261029，恰好六模型。不要把战略 style ID 当战术名，不擅改规则和模型。
- 规则修改需用户授权。freeze-manifest.json 与历史冻结 ZIP 保留原数据及执行来源；native-source-manifest.json 校验当前 C#、规则、模型、场景及资料的哈希和文件集合。禁止绕过；仅在明确授权的变更验收后显式更新 C# 清单。
- 回归：dotnet run --project tools/Magicians.Tooling -- test，以及 dotnet run --project tools/Magicians.Tooling -- client-regressions --godot <控制台exe>；图形过渡测试另运行 Scenes/Tests/V12TransitionRunner.tscn（需图形后端）。Godot4.7.2.NET、.NET8；TEMP/TMP 使用工作区 runtime/v12-temp。
- 开发工具统一为 tools/Magicians.Tooling；tools/sim_v12/rules 只保留 JSON 数据。已退休 Python 的精确工作区源码保存在 releases/v1.2/python-migration-baseline.zip，仅为校验和回放来源，不执行、不随游戏打包。
- 当前已发行包见 releases/client-v1.2.json；源码迁移不自动改变已发行包。构建见 docs/development.md。发布前验证导出日志、禁用 Python 的独立包烟测与 integrity.json。
- 旧版源码、研究报告及旧发行包已压缩归档到项目外 D:/Magicians!/_history。日常任务不扫描、解压或引用旧归档。只以本文件、README、当前规则与源码为准。
- 不提交本机缓存、日志、用户配置、密钥、历史大包。不要恢复被清理的旧客户端/文档。
