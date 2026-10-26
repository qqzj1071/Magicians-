# Magicians! 单人模式第一切片客户端技术设计

版本：0.1  
日期：2026-10-24  
目标引擎：Godot 4.7 .NET  
目标语言：C#  
状态：设计阶段，未开始实现

## 1. 目标与范围

第一切片用于验证一条可玩的单人赛事闭环：玩家带领自己的角色，与三名 AI 参加四人赛事，完成一次构筑轮、两场一对一战斗，并在战斗结束后自动结算赛事生命。

本切片包含：

- 四名参赛者：1 名人类玩家、3 名 AI。
- 每名参赛者初始 100 点赛事生命。
- 一次完整的构筑阶段。
- 基础牌组和基础牌候选。
- 玩家和 AI 的卡牌抽选、购买、研习点消耗与有限的牌组调整。
- 构筑结束后生成两两配对。
- 两场一对一战斗。
- 基于战斗结果和胜方剩余战斗生命的赛事生命扣除。
- 结果界面和本轮事件日志。
- 纯色、空白卡面和简单几何图形占位资源。

本切片暂不包含：

- 多轮赛事与淘汰流程。
- 五系专精、路线传奇、复杂传奇和混合元素效果。
- 完整共享池概率与完整构筑保底。
- 网络连接、房间系统和断线重连。
- 完整动画、音效和正式美术资源。

第一切片必须保留后续扩展所需的命令、事件、快照和控制器接口，不能把规则写进 UI 回调或动画脚本。

## 2. 规则依据与实现边界

规则数据以以下文件为准：

- `releases/v1.0/cards.json`：唯一卡牌数据源。
- `releases/deckbuilding-v1.0/README.md`：当前构筑规则。
- `docs/combat/resolution-order.md`：战斗同步结算顺序。
- `docs/combat/damage-model.md`：伤害计算模型。
- `docs/combat/numeric-standards.md`：数值规范。

`docs/multiplayer.md` 是多人产品草案，其中的旧赛事生命和扣血描述不能覆盖 v1.0 规则。

第一切片允许使用“基础牌子集”，但必须使用正式卡牌数据中的卡牌定义。未实现的卡牌效果不得静默当作已实现效果；应在数据加载时标记为 `UnsupportedInSlice1`，并阻止其进入本切片候选池。

## 3. 用户流程

```text
启动
  -> 主菜单
  -> 开始单人第一切片
  -> 初始化四名参赛者和固定随机种子
  -> 公布两两配对
  -> 展示本轮构筑候选
  -> 玩家选择购买、跳过或结束构筑
  -> AI 依次完成构筑
  -> 显示公开牌组摘要
  -> 玩家确认战斗
  -> 两场战斗并行逻辑结算、顺序展示
  -> 两场战斗完成后自动扣除赛事生命
  -> 显示本轮结果
  -> 返回主菜单或重新开始
```

AI 可以在玩家操作期间完成计算，但其结果必须通过同样的规则命令处理器提交，不能直接修改牌组或战斗状态。

## 4. 推荐项目结构

```text
Magicians!/
  project.godot
  Data/
    slice1/
      slice1-card-pool.json
      scenario.json
    v1.0/
      manifest.json
  Scenes/
    Boot/Boot.tscn
    MainMenu/MainMenu.tscn
    Match/Match.tscn
    Draft/DraftBoard.tscn
    Combat/CombatBoard.tscn
    Results/MatchResults.tscn
    Common/CardView.tscn
  Scripts/
    Core/
      Cards/
      Draft/
      Combat/
      Match/
      Common/
    Application/
      GameSession.cs
      MatchCoordinator.cs
      PhaseController.cs
    AI/
      IDraftPolicy.cs
      ICombatPolicy.cs
      Slice1DraftPolicy.cs
      Slice1CombatPolicy.cs
    Presentation/
      BootController.cs
      MainMenuController.cs
      DraftBoardController.cs
      CombatBoardController.cs
      ResultsController.cs
      EventLogController.cs
  Tests/
    Core/
    Scenarios/
```

第一切片通过 `Data/slice1/scenario.json` 和 `Data/slice1/slice1-card-pool.json` 引用现有冻结卡表的受控子集，不复制或修改 `releases/v1.0/cards.json`。

## 5. 核心状态模型

### 5.1 赛事状态

```csharp
public sealed record MatchState(
    string MatchId,
    int Round,
    MatchPhase Phase,
    int Seed,
    IReadOnlyDictionary<string, PlayerState> Players,
    IReadOnlyList<Pairing> Pairings,
    IReadOnlyList<BattleResult> BattleResults,
    IReadOnlyList<GameEvent> EventLog
);
```

第一切片只有 `Round = 1`，但保留轮次字段，避免后续多轮改写状态协议。

### 5.2 玩家状态

```csharp
public sealed record PlayerState(
    string PlayerId,
    PlayerKind Kind,
    int TournamentLife,
    DeckState Deck,
    DraftState Draft,
    PublicPlayerInfo PublicInfo
);
```

`TournamentLife` 与战斗中的 `CombatState.Life` 必须分开保存。

### 5.3 牌组状态

```csharp
public sealed record DeckState(
    IReadOnlyList<CardInstance> Cards,
    IReadOnlyList<CardInstance> DrawPile,
    IReadOnlyList<CardInstance> DiscardPile,
    IReadOnlyList<CardInstance> ExhaustedCards
);
```

基础牌组使用策划案中的 8 张起始牌：攻击强化×2、防御强化×2、护盾、检索附魔、短促、重洗。每张实体牌必须有唯一 `InstanceId`，不能只用卡牌名称表示。

### 5.4 构筑状态

```csharp
public sealed record DraftState(
    int Round,
    int StudyPoints,
    int RefreshesUsed,
    IReadOnlyList<OfferSlot> Offers,
    IReadOnlyList<string> PurchasedCardIds,
    bool IsCompleted
);
```

第一切片只开放基础牌和有限的普通牌候选，构筑流程仍保留 `StudyPoints`、刷新次数和候选槽位字段。

### 5.5 战斗状态

```csharp
public sealed record CombatState(
    string BattleId,
    string PlayerA,
    string PlayerB,
    int ActionValue,
    CombatantState A,
    CombatantState B,
    IReadOnlyList<PendingEffect> PendingEffects,
    bool IsFinished
);
```

`CombatState` 不包含 Godot 节点引用。动画节点只能根据事件读取它。

## 6. 命令和事件

### 6.1 构筑命令

```text
StartDraft
BuyCard(playerId, offerSlotId)
SkipOffer(playerId, offerSlotId)
RefreshOffers(playerId)
FinishDraft(playerId)
```

第一切片可先不开放删除、专精和路线命令，但接口应预留：

```text
RemoveCard
ChooseSpecialization
ChooseRoute
ReplaceRoute
```

### 6.2 战斗命令

```text
StartBattle
SubmitCombatAction(playerId, action)
PassCombatWindow(playerId)
FinishCombat
```

第一切片的 `CombatAction` 至少支持：

- 出牌实例；
- 结束当前出牌队列；
- 跳过窗口。

### 6.3 事件

建议事件类型：

```text
MatchStarted
DraftStarted
OfferGenerated
CardPurchased
DraftCompleted
PairingsPublished
BattleStarted
CardPlayed
ProjectileResolved
DamageApplied
BattleFinished
TournamentLifeChanged
RoundFinished
```

事件必须包含 `MatchId`、`Round`、`Sequence` 和产生事件时的状态哈希，便于回放与网络同步。

## 7. 赛事协调器

`MatchCoordinator` 是第一切片的应用层入口，不负责绘制 UI。

```csharp
public interface IMatchCoordinator
{
    MatchState StartSinglePlayerSlice1(int seed);
    CommandResult<MatchState> Submit(IGameCommand command);
    MatchState GetState();
}
```

状态转换固定为：

```text
Setup
  -> Draft（进入时发布配对）
  -> Combat
  -> Settlement
  -> Finished
```

每个阶段只能接受属于该阶段的命令。非法阶段命令返回拒绝结果，不改变状态。

配对服务第一切片可以使用固定配对，并在构筑开始前发布：

```text
玩家 vs AI-1
AI-2 vs AI-3
```

但应通过 `IPairingService` 接口调用，后续再替换为完整的避免连续对战算法。

## 8. 构筑实现策略

第一切片的构筑重点是验证“候选—研习—购买—牌组更新”闭环，不提前实现所有 v1.0 生成约束。

第一切片使用 `Data/slice1/slice1-card-pool.json` 中独立的基础候选库存。候选生成时预留共享库存，购买后实体归玩家持有，跳过或结束构筑时未购买候选归还库存；初始八张牌不占候选库存。

建议配置文件 `Data/slice1/scenario.json`：

```json
{
  "round": 1,
  "initialTournamentLife": 100,
  "initialStudyPoints": 2,
  "offersPerPlayer": 4,
  "allowRefresh": false,
  "allowRemove": false,
  "allowSpecialization": false,
  "cardPool": "slice1-card-pool"
}
```

候选池只放入已经有明确事务实现的基础牌和少量普通牌。每次购买都必须检查：

- 候选槽位仍属于该玩家；
- 研习点足够；
- 玩家尚未持有同名牌，除非该牌是允许重复的基础牌；
- 卡牌在本切片能力范围内；
- 共享实体仍可用。

玩家与 AI 的构筑都走 `DraftCommandProcessor`。AI 只返回选择，处理器负责合法性和资源扣除。

## 9. 战斗实现策略

战斗核心必须采用固定随机种子和事件驱动结算。第一切片建议先支持：

- 1000 点战斗生命；
- 60 攻击、20 防御、0 护盾；
- 行动值 0、100、200……的抽牌窗口；
- 每次抽牌 5 张、获得 3 点战斗费用；
- 基础攻击和防御牌；
- 护盾牌；
- 基础飞弹伤害 `max(1, attack - defense)`；
- 同刻双方提交后统一结算；
- 双方可以在同一抽牌窗口连续提交多张牌，双方都结束出牌队列后才进入疲劳、发射和下一抽牌窗口；
- 战斗结束时记录胜方剩余生命。

第一切片暂时可以将尚未支持的复杂效果从候选池排除，但不能在通用解析器中用“忽略文本”代替效果实现。

战斗执行器接口：

```csharp
public interface ICombatEngine
{
    CombatState Start(CombatSetup setup);
    ResolutionResult Resolve(CombatState state, CombatCommand command);
}
```

执行器输出事件序列，UI 根据事件播放攻击、护盾和生命变化。

## 10. AI 接口

```csharp
public interface IDraftPolicy
{
    DraftDecision Choose(DraftObservation observation);
}

public interface ICombatPolicy
{
    CombatDecision Choose(CombatObservation observation);
}
```

第一切片的 AI 可以先使用确定性启发式：

- 构筑优先购买费用可承受且尚未持有的基础牌；
- 攻击牌和防御牌保持简单比例；
- 战斗中优先打出当前费用可用的基础牌；
- 生命低于阈值时优先护盾和防御；
- 没有合法牌时结束当前窗口。

后续接入训练好的 AI 时，只替换策略实现，不改动 `MatchCoordinator`、命令处理器和战斗引擎。

## 11. Godot 表现层

### 11.1 场景职责

```text
Boot.tscn       初始化数据、创建 GameSession
MainMenu.tscn   开始第一切片、退出
Match.tscn      持有整体 UI 和阶段切换
DraftBoard.tscn 显示候选、研习点和牌组
CombatBoard.tscn显示双方战斗状态和操作区
MatchResults.tscn显示两场战斗和赛事生命变化
```

### 11.2 UI 规则

- UI 只能调用 `IMatchCoordinator.Submit`。
- UI 不直接修改 `MatchState`。
- AI 的思考过程显示为“AI 行动中”，不显示私有决策细节。
- 事件日志显示公开事件，不泄露 AI 私有牌组。
- 动画跳过后，必须直接显示事件处理后的状态。

### 11.3 占位资源

- 卡牌使用 `PanelContainer`、`Label` 和纯色边框。
- 元素使用固定颜色映射。
- 战斗角色使用 `ColorRect` 或 `Polygon2D`。
- 发射物使用简单圆形或矩形。
- 没有正式美术资源时，不创建会影响规则的资源依赖。

## 12. 面向联网的边界

即使第一切片只运行本地单人模式，也应遵守以下约束：

1. 规则核心可以在 Headless 模式运行。
2. 玩家和 AI 都通过命令提交操作。
3. 状态由权威协调器生成。
4. 命令带有 `MatchId`、`Round`、`Phase`、`Sequence`。
5. 随机数由服务器可复现的种子流产生。
6. 事件和状态快照可序列化。
7. 客户端不提交伤害、胜负或扣血结果。
8. 私有牌组信息只发送给拥有者，公开信息单独建模。

建议先定义传输无关的 DTO：

```text
CommandDto
EventDto
MatchSnapshotDto
PlayerViewDto
PublicMatchViewDto
```

未来可以在 Godot 本地进程、局域网服务器和在线服务器之间复用同一套 DTO。

## 13. 验证计划

### 13.1 规则核心测试

- 四名玩家初始化后赛事生命均为 100。
- 每名玩家拥有正确的 8 张基础牌。
- 购买会扣除研习点并加入牌组。
- 不足研习点时购买被拒绝。
- 非法卡牌、重复卡牌和无效候选不会改变状态。
- 两场配对不会重复使用玩家。
- 基础伤害最低为 1。
- 同刻双方命令都会完成后再检查死亡。
- 战斗结果正确记录胜方剩余生命。
- 赛事生命扣除使用当前 v1.0 扣血公式。
- 固定种子重复运行时，事件序列和最终状态哈希一致。

### 13.2 场景测试

- 从主菜单可以启动并完成第一切片。
- 玩家可以完成构筑或跳过构筑。
- AI 可以自动完成构筑。
- 两场战斗均能进入结果页。
- 战斗结果页显示赛事生命变化。
- 跳过动画不会改变最终状态。

### 13.3 验收条件

第一切片完成的最低标准是：新玩家启动后无需编辑文件，能够在 Godot 内完成以下流程：

```text
开始单人模式
  -> 看见四名参赛者
  -> 购买至少一张基础牌
  -> 结束构筑
  -> 看见两两配对
  -> 完成两场战斗
  -> 看见每名参赛者的赛事生命扣除
  -> 看到本轮结束状态
```

同时，使用同一随机种子在 Headless 测试中重复运行，应得到相同的事件日志和状态哈希。

## 14. 实施顺序

1. 创建 C# 项目文件和 `Scripts`、`Scenes`、`Data`、`Tests` 目录。
2. 导入并校验冻结卡牌 JSON。
3. 实现 `CardDefinition`、`CardInstance` 和基础牌组初始化。
4. 实现 `MatchState`、命令、事件和阶段状态机。
5. 实现第一切片构筑候选和购买处理器。
6. 实现基础战斗状态、费用、抽牌和伤害结算。
7. 接入三名确定性 AI。
8. 完成赛事配对、战斗结果和扣血结算。
9. 创建最小 Godot 场景和占位 UI。
10. 编写 Headless 回归测试和固定种子验收场景。

在这些步骤完成前，不建议接入完整 253 张卡、复杂传奇效果或联网传输。第一切片的价值是确认规则核心、控制器接口和表现层之间的边界正确。
