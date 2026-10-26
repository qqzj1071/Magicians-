# 统一效果解析管线与全局结算顺序

## 全局结算顺序

```text
BeforePlay
  -> OnPlay
  -> AfterPlay
  -> BeforeDraw
  -> AfterDraw
  -> BeforeFire
  -> ProjectileCreated
  -> BeforeShieldSplit
  -> AfterShieldSplit
  -> AfterDamage
  -> AfterFire
  -> WindowClosed
  -> BattleFinished
```

同一时机内按 `Priority` 升序、`ResolverId` 字典序执行。效果解析器只返回资源快照和事件，不直接修改 `CombatState`；引擎在一个事务中提交资源变化、事件和随机流变化。

## 全局资源

`CombatResourceState` 统一保存生命、护盾、攻击、防御、费用、五系元素层、计数器和状态集合。后续的负面效果、余烬/毒层、路线资源和一次性触发器都应进入这里，避免继续向 `CombatantState` 添加互相独立的临时字段。

## 阻断规则

没有注册 `ICardEffectResolver` 的卡牌不能进入效果管线，会返回 `UnsupportedCardEffect`。注册表和全量卡池闸门继续共同控制客户端是否可以切换到全量卡池。

当前先使用基础卡牌适配器验证管线顺序；基础引擎的旧效果仍在逐步迁移，复杂效果不会被空实现放行。

毒伤触发顺序：每次 100 行动值抽牌阶段前，先按来源毒附魔层 × 目标当前毒层 × 目标最大生命 1000 × 1%（专精前）/2%（专精后）计算毒伤，再处理毒层自然衰减，最后进入抽牌阶段。毒伤跳过护盾，按目标防御的 50% 结算。
