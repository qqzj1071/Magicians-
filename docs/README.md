# Magicians! 文档中心

> 版本：v0.5 规则草案  
> 项目：Godot 4.7 / C#  
> 状态：规则与卡表整理阶段；战斗原型尚未开始。

---

## 1. 文档架构

```text
docs/
  README.md                 本文件：文档导航
  game-concept.md           对外介绍 / 招募用概念文档
  overview.md               整体规则：世界观、模式、一局流程、术语

  combat/
    rules.md                战斗规则：行动值、费用、伤害、护盾、毒、疲劳
    resolution-order.md     同步结算规则书：快照、出牌队列、飞弹、反应、死亡与程序验收
    ai.md                   单人对战 AI、训练路线、工程结构

  deckbuilding/
    rules.md                牌组构筑：初始牌、构筑序列、选牌、专精、传奇 3 选 1

  cards/
    README.md               卡牌系统总则、初始 8 张、稀有度、费用、费效比
    legendary-design.md     传奇设计原则、五系路线矩阵、3 选 1
    fire/                   示例：五系文件夹结构相同
      README.md             元素定位与文件索引
      common.md             普通附魔
      rare.md               稀有附魔与路线支撑
      epic.md               史诗附魔与路线支撑
      legendary.md          传奇（含 5 层与路线传奇）
      specialization.md     专精强卡
    water/                  同 fire 结构
    earth/                  同 fire 结构
    wind/                   同 fire 结构
    poison/                 同 fire 结构
    generic/
      README.md             通用卡牌说明
      common.md             基础牌模板
      rare.md               过牌/检索/洗牌/攻防等通用牌
      epic.md               高强度通用效果
      legendary.md          通用传奇

  multiplayer.md            4 人淘汰、配对、幽灵、自动/手动池
  open-questions.md         待定项与决策记录
  archive/                  旧版文档，仅作历史参考
```

---

## 2. 推荐阅读顺序

### 新合作者

1. `game-concept.md`：先看这是什么游戏。
2. `overview.md`：一局怎么走、有哪些模式。
3. `combat/rules.md`：战斗怎么打。
4. `deckbuilding/rules.md`：牌组怎么构筑。
5. `cards/README.md`：卡牌系统与初始牌。
6. 对应元素文件：`cards/fire/README.md` 等。

### 程序

先读 `combat/resolution-order.md`，确定执行模型与死亡检查边界，再阅读下面的基础规则和卡表。

1. `combat/rules.md`
2. `deckbuilding/rules.md`
3. `combat/ai.md`
4. `cards/README.md`
5. `open-questions.md`

### 卡牌 / 数值设计

1. `cards/README.md`
2. `cards/legendary-design.md`
3. 五个元素文件
4. `open-questions.md`

### 美术 / UI

1. `game-concept.md`
2. `overview.md`
3. `combat/rules.md` 的 UI 可读性部分
4. `cards/README.md`
5. 各元素文件中的视觉关键词

---

## 3. 单一事实来源

- 整体规则：`overview.md`
- 战斗规则：`combat/rules.md`
- 同步结算与执行顺序：`combat/resolution-order.md`（与旧时序冲突时优先）
- 构筑规则：`deckbuilding/rules.md`
- 卡牌总则与初始牌：`cards/README.md`
- 单系卡牌：`cards/<element>/README.md` 及同文件夹下的稀有度文件
- 传奇设计：`cards/legendary-design.md`
- 待定项：`open-questions.md`

旧版 `game-design.md`、`cards.md`、`legendaries.md` 已移到 `archive/`，不再作为当前依据。

---

## 4. 当前项目状态

- 规则版本：v0.5。
- 卡表版本：v0.5。
- 已确定：4 人淘汰、1000 战斗生命 / 50 赛事血量、3 费抽牌、五系附魔、专精、传奇 3 选 1、幽灵、1500 疲劳。
- 未完成：全卡数值模拟与重算、1v1 战斗原型、AI 构筑逻辑。

---

## 5. 近期目标

1. 完成五系传奇卡与向下延伸的史诗/稀有卡。
2. 按 1000 血尺度重算普通/稀有/史诗数值。
3. 做 1v1 战斗实验室：抽牌、费用、附魔、伤害、疲劳。
4. 做 4 人 + 3 AI 的完整单人流程。
5. 最后做多人自动池/手动池。

---

## 6. 文档维护规则

- 规则改动先改对应单一事实来源，再更新 `open-questions.md`。
- 新增卡牌写入对应元素文件，不写进总表。
- 传奇卡写入 `cards/legendary-design.md` 的路线矩阵与 `cards/<element>/legendary.md`。
- 旧方案不再直接修改，移到 `archive/` 并注明日期。
