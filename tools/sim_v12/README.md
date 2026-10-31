# v1.2 规则数据

此目录只保留 rules/ JSON 和 fixtures/ 测试策略。唯一执行内核为 Scripts/Native；开发工具为 tools/Magicians.Tooling，不再运行Python。

当前183张卡牌、677库存，四人赛事。全部火系卡（含专精/传奇）统一计作火系附魔牌；实现见 Magicians.Native.Card.enchantment。运行回归：`dotnet run --project tools/Magicians.Tooling -- test`。

六模型入口为 SixStyles.load_policy，发布模型位于 releases/ai-v1.2-six-styles-20261029。fixtures中的两份小型策略仅用于算法回归。训练使用新输出目录和独立训练/验证/终测，默认不部署候选。详见 docs/development.md。
