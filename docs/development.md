# v1.2 开发流程

## 环境与运行

Godot 4.7.2 .NET、.NET 8 SDK、Python 3.12。用 Godot 打开 project.godot。可用 MAGICIANS_PYTHON 指定解释器。发行包内置 Python，无需玩家配置。

## 当前结构

- Scripts/Presentation/V12MatchController.cs：构筑、战斗、卡牌与复盘界面。
- tools/client_v12/match.py：常驻赛事适配器；tools/sim_v12 为唯一战斗与构筑规则内核。
- releases/v1.2：卡牌快照、校验清单；releases/ai-v1.2-six-styles-20261029：六风格发布模型。
- Data/Presentation/card-art.json：纯美术槽位，不包含旧版规则副本。
- docs/cards-v1.2/*-name-map.json：五系定稿展示名来源；运行卡名继续作为稳定规则 ID。新增或修改展示名后，先运行 `python tools/build_v12_presentation.py`，由五系映射生成 Data/Presentation/card-display.json，再验证客户端。
- Data/Presentation/card-display.json：通过 V12CardPresentation 接入卡面、路线、日志与卡牌提示；显示名与规则 ID 分开。小字保留 display_in_match=false，不在局内显示。

## 验证

```powershell
powershell -ExecutionPolicy Bypass -File tools/run_v12_client_regressions.ps1
```

脚本构建.NET、验证模拟器与客户端协议、检查冻结数据，并运行完整赛事、主菜单、分辨率、删牌和选择测试。图形后端另运行 Scenes/Tests/V12TransitionRunner.tscn，覆盖买牌/结束购买/出牌过渡。测试输出写入 runtime，不能提交。

## Windows 离线包

```powershell
python tools/installer/build_v12_portable.py --godot <Godot控制台exe> --template <同版本Windows导出模板exe> --python-runtime <Python3.12嵌入运行时目录> --licenses <依赖许可证目录> --output <新发行目录>
```

本机依赖位于项目外 D:/Magicians!/_tools/release-runtime，不再依赖旧安装包。其他机器使用同版本 Godot Windows 导出模板和官方 Python 3.12 嵌入运行时，并随包保留许可证。不要把本机绝对路径当作规则。

导出后运行 `Magicians.exe --headless -- --release-smoke`，要求日志出现 V12_PACKAGED_OK 且退出码0；校验 integrity.json 后压缩完整目录，附 SHA256。桌面快捷方式使用 tools/update_desktop_shortcut.ps1。

## 历史与版本边界

旧版源码/报告已压缩到项目外 _history，逐文件校验完成后从活动项目删除；旧安装包使用去重归档，files.json 映射原路径到 objects/SHA256。不要将旧归档作为开发上下文。当前 v1.2 包完全取代 v1.1。
