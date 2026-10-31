# v1.2 C# 开发流程

开发需要 Godot 4.7.2 .NET 与 .NET 8 SDK。用 Godot 打开 project.godot。游戏与开发工具不调用 Python；当前无Python发行包见 releases/client-v1.2.json。

## 结构

- Scripts/Native：唯一战斗、构筑、赛事和AI规则内核，独立于Godot。
- Scripts/Application：异步赛事接口；Scripts/Presentation 与 Scenes：现有界面和输入。
- tools/Magicians.Tooling：独立C#命令行工具，共享Native源码；Godot编译排除tools目录。
- tools/sim_v12/rules：现行规则JSON数据；releases/v1.2：卡牌、冻结证据及执行清单。
- releases/ai-v1.2-six-styles-20261029：六个发布模型，不随普通训练替换。
- 所有运行标识与展示名称统一使用最新定稿卡名；Data/Presentation/card-flavor.json保存五系25条文案，现有卡面及提示继续显示。

## 构建与验证

```powershell
dotnet build 'Magicians!.csproj'
dotnet run --project tools/Magicians.Tooling -- verify
dotnet run --project tools/Magicians.Tooling -- test
dotnet run --project tools/Magicians.Tooling -- client-regressions --godot <Godot控制台exe>
```

完整回归包括精确分数、兼容随机序列、机制、业务操作、当前Python基线的固定数据回放、协议隐私及训练算法/统计。测试运行本身无需Python。场景回归覆盖完整赛事、生命周期、主菜单、卡面、删牌、选择和战斗集成。另用图形后端运行 Scenes/Tests/V12TransitionRunner.tscn；文案展示可运行 V12FlavorRunner.tscn。临时文件使用工作区 runtime/v12-temp，日志和编译缓存不提交。

## 资料与训练

```powershell
dotnet run --project tools/Magicians.Tooling -- build-presentation --check
dotnet run --project tools/Magicians.Tooling -- build-catalogue --check
dotnet run --project tools/Magicians.Tooling -- audit-layers --check
dotnet run --project tools/Magicians.Tooling -- audit-cards
dotnet run --project tools/Magicians.Tooling -- sim --games 5 --seed 1200 --out runtime/rooms-new
dotnet run --project tools/Magicians.Tooling -- train --mode six --out runtime/six-new
```

训练支持 mechanism、thin、medium、free、dual、outcome、element、element-paired、population、six。输出必须为新目录，模型输入显式指定或使用发布模型；普通训练不部署候选。--deploy须通过原有选择门槛及完整性校验。保留独立训练、验证与终测，缩预算流程检查不代表完成大规模训练。help列出全部命令。

## 冻结边界

卡牌规则及数值修改需明确授权。旧freeze-manifest与原冻结ZIP保留不变；python-migration-baseline.zip封存迁移前当前工作区源码，退休清单核对归档内逐文件哈希，既不执行归档，也不把未提交修改当成某个Git提交。

native-source-manifest.json保护当前C#实现、规则、模型、展示资料和源文件集合。缺失、新增或改动均拒绝。首次封存用 freeze --create-native-manifest；只有明确授权的修改验收后才用 freeze --refresh-native-manifest。禁止为通过未知差异而自动重封。具体来源与验证边界见 csharp-migration.md。

## Windows离线包

```powershell
dotnet run --project tools/Magicians.Tooling -- build-portable --godot <Godot控制台exe> --template <同版本Windows导出模板exe> --licenses <许可证目录> --output <项目外新目录>
dotnet run --project tools/Magicians.Tooling -- audit-package --package <完整解压目录> --smoke
dotnet run --project tools/Magicians.Tooling -- archive --package <目录> --output <新ZIP路径>
```

导出检查完整性并在禁用Python的环境中运行完整赛事烟测，要求V12_PACKAGED_OK与退出码0。不携带Python、开发源码或历史归档；保留Godot/.NET许可证。玩家完整解压后运行Magicians.exe，无需安装开发环境。不要只分享快捷方式或单个exe。

桌面入口使用C#命令：

dotnet run --project tools/Magicians.Tooling -- desktop-shortcut --package <完整解压目录>

工作区目录：Magicians!为唯一活动源码；_installers保存当前程序和ZIP；_tools、.nuget与.dotnet-home为.NET/Godot开发依赖；runtime保存本次验证证据；_history保存只读历史与原始命名资料。
