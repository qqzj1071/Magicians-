# Magicians! v1.2 — 当前项目约束

v1.2 已于 2026-10-30 验收，完全替代 v1.1。主入口 Scenes/Boot/Boot.tscn → MainMenu → Scenes/V12/SinglePlayer.tscn。不存在旧客户端回退入口。

- 权威规则：tools/sim_v12，183张卡牌、677份库存；客户端 tools/client_v12/match.py 在独立常驻 Python 进程暂停/恢复四人赛事。C# 只负责界面与输入。
- 卡牌：releases/v1.2/cards.json 与 docs/cards-v1.2。使用旧运行卡名，未来通过 V12CardPresentation 的 DisplayName/DisplayRules 接口替换。全部火系卡（含专精/传奇）属于火系附魔牌；ability 与打出后移出规则独立。
- AI：releases/ai-v1.2-six-styles-20261029，恰好六模型。不要把战略 style ID 当战术名，不擅改规则和模型。
- 规则修改需用户授权，并维护 freeze-manifest.json 的当前执行哈希；历史冻结 ZIP 是溯源基线，不代表最新执行修正。保留校验，禁止绕过。
- 回归：powershell -File tools/run_v12_client_regressions.ps1；图形过渡测试另运行 Scenes/Tests/V12TransitionRunner.tscn（需图形后端）。Python3.12、Godot4.7.2.NET、.NET8；TEMP/TMP 使用工作区 runtime/v12-temp。
- 当前发行：releases/client-v1.2.json；构建见 docs/development.md。发布前验证导出日志、内置Python烟测、integrity.json。
- 旧版源码、研究报告及旧发行包已压缩归档到项目外 D:/Magicians!/_history。日常任务不扫描、解压或引用旧归档。只以本文件、README、当前规则与源码为准。
- 不提交本机缓存、日志、用户配置、密钥、历史大包。不要恢复被清理的旧客户端/文档。
