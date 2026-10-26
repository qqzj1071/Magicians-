# Magicians! 规则核心接口草案

版本：0.1  
日期：2026-10-24  
适用范围：单人模式第一切片  
实现语言：C#  
运行环境：Godot 4.7 .NET

本文件定义规则核心与 Godot、AI、回放和未来联网层之间的接口边界。它是接口草案，不包含具体规则实现，也不修改冻结卡牌与构筑数据。

## 1. 设计原则

1. 规则核心不引用 Godot 类型，不继承 `Node`、`Resource` 或 `Control`。
2. UI、AI、网络客户端都通过命令提交行为。
3. 规则核心返回新状态、事件和拒绝原因。
4. 随机数由可注入的确定性随机源提供。
5. 事件日志可以重放，状态可以序列化和生成哈希。
6. 玩家和 AI 使用相同的命令校验路径。
7. 对手私有信息通过视图投影隐藏，不直接从完整状态读取。
8. 第一切片只实现基础牌和已验证效果，但接口不限制后续卡牌类型。

## 2. 推荐命名空间

```text
Magicians.Core.Common
Magicians.Core.Cards
Magicians.Core.Draft
Magicians.Core.Combat
Magicians.Core.Match
Magicians.Core.AI
Magicians.Core.Serialization
```

建议将规则核心做成独立 C# 项目或 Godot 项目内的独立程序集。Godot 表现层只能引用核心程序集，核心程序集不能反向引用 Godot。

## 3. 通用标识和结果类型

```csharp
namespace Magicians.Core.Common;

public readonly record struct MatchId(string Value);
public readonly record struct PlayerId(string Value);
public readonly record struct BattleId(string Value);
public readonly record struct CardId(string Value);
public readonly record struct CardInstanceId(string Value);
public readonly record struct CommandSequence(long Value);

public enum PlayerKind
{
    Human,
    Ai,
    Ghost
}

public enum MatchPhase
{
    Setup,
    Draft,
    Pairing,
    Combat,
    Settlement,
    Finished
}

public sealed record Rejection(
    string Code,
    string Message
);

public sealed record CommandResult<TState>(
    bool Accepted,
    TState State,
    IReadOnlyList<GameEvent> Events,
    Rejection? Rejection,
    string StateHash
);
```

`Message` 用于开发日志和调试，UI 应优先根据 `Code` 显示本地化文本。

## 4. 命令接口

```csharp
public interface IGameCommand
{
    MatchId MatchId { get; }
    PlayerId Issuer { get; }
    MatchPhase ExpectedPhase { get; }
    CommandSequence Sequence { get; }
}

public interface ICommandProcessor<TState>
{
    CommandResult<TState> Apply(TState state, IGameCommand command);
}
```

第一切片的构筑命令：

```csharp
public sealed record StartDraftCommand(
    MatchId MatchId,
    PlayerId Issuer,
    CommandSequence Sequence
) : IGameCommand
{
    public MatchPhase ExpectedPhase => MatchPhase.Setup;
}

public sealed record BuyCardCommand(
    MatchId MatchId,
    PlayerId Issuer,
    string OfferSlotId,
    CommandSequence Sequence
) : IGameCommand
{
    public MatchPhase ExpectedPhase => MatchPhase.Draft;
}

public sealed record SkipOfferCommand(
    MatchId MatchId,
    PlayerId Issuer,
    string OfferSlotId,
    CommandSequence Sequence
) : IGameCommand
{
    public MatchPhase ExpectedPhase => MatchPhase.Draft;
}

public sealed record FinishDraftCommand(
    MatchId MatchId,
    PlayerId Issuer,
    CommandSequence Sequence
) : IGameCommand
{
    public MatchPhase ExpectedPhase => MatchPhase.Draft;
}
```

多轮构筑命令：

```csharp
public sealed record RefreshOffersCommand(...) : IGameCommand;
public sealed record RemoveCardCommand(...) : IGameCommand;
public sealed record ChooseSpecializationCommand(...) : IGameCommand;
public sealed record ChooseRouteCommand(...) : IGameCommand;
public sealed record ReplaceRouteCommand(...) : IGameCommand;

public sealed record BeginRoundDraftCommand(...) : IGameCommand;
public sealed record AdvanceSettlementCommand(...) : IGameCommand;
```

命令处理器会根据场景开关、轮次和牌组状态返回明确拒绝码，例如
`RefreshLimitReached`、`RemoveLimitReached`、`SpecializationRequirement`、
`RouteRequiresSpecialization` 和 `LegendaryLimitReached`，不会静默忽略。

第一切片的战斗命令：

```csharp
public sealed record StartBattleCommand(
    MatchId MatchId,
    PlayerId Issuer,
    BattleId BattleId,
    CommandSequence Sequence
) : IGameCommand
{
    public MatchPhase ExpectedPhase => MatchPhase.Combat;
}

public sealed record PlayCardCommand(
    MatchId MatchId,
    PlayerId Issuer,
    BattleId BattleId,
    CardInstanceId Card,
    CommandSequence Sequence
) : IGameCommand
{
    public MatchPhase ExpectedPhase => MatchPhase.Combat;
}

public sealed record PassCombatWindowCommand(
    MatchId MatchId,
    PlayerId Issuer,
    BattleId BattleId,
    CommandSequence Sequence
) : IGameCommand
{
    public MatchPhase ExpectedPhase => MatchPhase.Combat;
}
```

## 5. 事件接口

```csharp
public abstract record GameEvent(
    MatchId MatchId,
    int Round,
    long Sequence,
    string StateHash
);

public sealed record MatchStartedEvent(
    MatchId MatchId,
    int Round,
    long Sequence,
    string StateHash,
    int Seed,
    IReadOnlyList<PlayerId> Players
) : GameEvent(MatchId, Round, Sequence, StateHash);

public sealed record DraftStartedEvent(
    MatchId MatchId,
    int Round,
    long Sequence,
    string StateHash,
    IReadOnlyList<PlayerId> Players
) : GameEvent(MatchId, Round, Sequence, StateHash);

public sealed record OfferGeneratedEvent(
    MatchId MatchId,
    int Round,
    long Sequence,
    string StateHash,
    PlayerId Owner,
    IReadOnlyList<OfferSlotView> Offers
) : GameEvent(MatchId, Round, Sequence, StateHash);

public sealed record CardPurchasedEvent(
    MatchId MatchId,
    int Round,
    long Sequence,
    string StateHash,
    PlayerId Player,
    CardInstanceId Card,
    string OfferSlotId
) : GameEvent(MatchId, Round, Sequence, StateHash);

public sealed record PairingsPublishedEvent(
    MatchId MatchId,
    int Round,
    long Sequence,
    string StateHash,
    IReadOnlyList<PairingView> Pairings
) : GameEvent(MatchId, Round, Sequence, StateHash);

public sealed record CardPlayedEvent(
    MatchId MatchId,
    int Round,
    long Sequence,
    string StateHash,
    BattleId Battle,
    PlayerId Player,
    CardInstanceId Card
) : GameEvent(MatchId, Round, Sequence, StateHash);

public sealed record DamageAppliedEvent(
    MatchId MatchId,
    int Round,
    long Sequence,
    string StateHash,
    BattleId Battle,
    PlayerId Source,
    PlayerId Target,
    int ShieldDamage,
    int LifeDamage
) : GameEvent(MatchId, Round, Sequence, StateHash);

public sealed record BattleFinishedEvent(
    MatchId MatchId,
    int Round,
    long Sequence,
    string StateHash,
    BattleId Battle,
    PlayerId? Winner,
    int WinnerRemainingLife,
    bool DoubleElimination
) : GameEvent(MatchId, Round, Sequence, StateHash);

public sealed record TournamentLifeChangedEvent(
    MatchId MatchId,
    int Round,
    long Sequence,
    string StateHash,
    PlayerId Player,
    int PreviousLife,
    int NewLife,
    int Damage
) : GameEvent(MatchId, Round, Sequence, StateHash);
```

事件应描述已经发生的事实，不描述动画指令。比如 `DamageAppliedEvent` 是规则结果，飞弹移动动画由表现层自行决定。

## 6. 卡牌接口

```csharp
public enum CardRarity
{
    Common,
    Rare,
    Epic,
    Legendary,
    Specialization
}

public enum CardKind
{
    Normal,
    Specialization,
    RouteLegendary,
    Legendary
}

public sealed record CardDefinition(
    CardId Id,
    string Name,
    string Element,
    CardRarity Rarity,
    CardKind Kind,
    int Cost,
    int Attack,
    int Defense,
    int Layers,
    bool IsAbility,
    string RulesText,
    string? RouteSupport,
    bool SupportedInSlice1
);

public sealed record CardInstance(
    CardInstanceId InstanceId,
    CardId DefinitionId,
    PlayerId Owner
);

public interface ICardDatabase
{
    CardDefinition Get(CardId id);
    bool TryGet(CardId id, out CardDefinition definition);
    IReadOnlyList<CardDefinition> AllSupportedCards { get; }
    string DataVersion { get; }
}
```

卡牌定义和实体必须分离：定义描述卡牌规则，实体描述某个玩家持有的具体副本。共享池库存也应按 `CardInstanceId` 追踪。

## 7. 赛事和玩家状态

```csharp
public sealed record MatchState(
    MatchId Id,
    int Round,
    MatchPhase Phase,
    int Seed,
    ulong RandomState,
    int InitialStudyPoints,
    int OffersPerPlayer,
    long EventSequence,
    IReadOnlyDictionary<PlayerId, PlayerState> Players,
    IReadOnlyDictionary<string, int> SharedCardInventory,
    IReadOnlyList<Pairing> Pairings,
    IReadOnlyList<BattleResult> BattleResults,
    IReadOnlyList<GameEvent> EventLog,
    IReadOnlyList<Pairing> PairingHistory,
    IReadOnlyList<RoundSummary> RoundHistory,
    IReadOnlyDictionary<PlayerId, int> NextRoundStudyPoints,
    IReadOnlyDictionary<PlayerId, PlayerState> GhostSnapshots
);

public sealed record PlayerState(
    PlayerId Id,
    PlayerKind Kind,
    int TournamentLife,
    DeckState Deck,
    DraftState Draft,
    PublicPlayerInfo PublicInfo
);

public sealed record PublicPlayerInfo(
    string DisplayName,
    string? Specialization,
    string? Route,
    bool IsEliminated
);

public sealed record Pairing(
    BattleId BattleId,
    PlayerId PlayerA,
    PlayerId PlayerB
);
```

第一切片允许固定配对 `Human vs AI-1`、`AI-2 vs AI-3`，但应通过 `IPairingService` 提供，不能把配对规则写死在 UI。

## 8. 构筑接口

```csharp
public sealed record DraftState(
    int Round,
    int StudyPoints,
    int RefreshesUsed,
    IReadOnlyList<OfferSlot> Offers,
    IReadOnlySet<CardInstanceId> PurchasedCards,
    bool Completed
);

public sealed record OfferSlot(
    string SlotId,
    CardInstance Card,
    int Cost,
    bool IsPurchased
);

public sealed record DraftObservation(
    PlayerId Player,
    DraftState Draft,
    DeckState Deck,
    PublicMatchView MatchView
);

public interface IDraftEngine
{
    DraftState Start(DraftSetup setup);
    CommandResult<MatchState> Apply(MatchState state, IGameCommand command);
    bool IsLegal(MatchState state, IGameCommand command, out Rejection? rejection);
}

public interface IDraftPolicy
{
    DraftDecision Choose(DraftObservation observation);
}

public sealed record DraftDecision(
    DraftDecisionKind Kind,
    string? OfferSlotId
);

public enum DraftDecisionKind
{
    Buy,
    Skip,
    Refresh,
    Finish
}
```

`IDraftEngine` 负责规则合法性，`IDraftPolicy` 只负责“选择什么”。玩家 UI 和 AI 都应最终产生相同的 `IGameCommand`。

## 9. 战斗接口

```csharp
public sealed record CombatantState(
    PlayerId Player,
    int Life,
    int MaxLife,
    int Attack,
    int Defense,
    int Shield,
    int Energy,
    int NextDrawActionValue,
    int NextFireActionValue,
    DeckState Deck,
    IReadOnlyList<CardInstance> CurrentPool
);

public sealed record CombatState(
    BattleId Battle,
    int ActionValue,
    CombatantState A,
    CombatantState B,
    bool IsFinished,
    PlayerId? Winner
);

public sealed record CombatObservation(
    BattleId Battle,
    PlayerId Player,
    CombatState VisibleState
);

public interface ICombatEngine
{
    CombatState Start(CombatSetup setup);
    CombatResolution Submit(CombatState state, CombatCommand command);
    IReadOnlyList<CardInstance> GetSearchCandidates(CombatState state, PlayerId player);
}

public interface ICombatPolicy
{
    CombatDecision Choose(CombatObservation observation);
}

public sealed record CombatCommand(
    BattleId Battle,
    PlayerId Player,
    long ExpectedRevision,
    CombatAction Action
);

public enum CombatActionKind
{
    PlayCard,
    EndWindow
}

public sealed record CombatAction(
    CombatActionKind Kind,
    CardInstanceId? Card,
    CardInstanceId? SearchTarget
);

public sealed record CombatResolution(
    bool Accepted,
    CombatState State,
    IReadOnlyList<GameEvent> Events,
    Rejection? Rejection
);
```

第一切片的战斗引擎只需实现基础牌、基础费用、抽牌、护盾和基础飞弹伤害，但接口应允许以后增加副弹、毒层、专精、路线和复活效果。

当前实现采用同步出牌队列：双方可以在同一个抽牌窗口连续提交多张 `PlayCard`，只有双方都提交 `EndWindow` 后才执行疲劳、到期效果、发射组和下一抽牌窗口。双方各自的待提交队列属于私有权威状态，网络视图不得直接转发给对手。

## 10. 赛事扣血接口

```csharp
public interface ITournamentDamageCalculator
{
    int CalculateLoss(int round, int winnerRemainingCombatLife);
    int CalculateDoubleEliminationLoss(int round);
}

public interface ISettlementService
{
    SettlementResult SettleBattle(
        MatchState state,
        BattleResult battleResult);
}

public sealed record BattleResult(
    BattleId Battle,
    PlayerId PlayerA,
    PlayerId PlayerB,
    PlayerId? Winner,
    int WinnerRemainingCombatLife,
    bool DoubleElimination
);

public sealed record SettlementResult(
    MatchState State,
    IReadOnlyList<GameEvent> Events
);
```

第一切片的扣血计算必须读取当前 v1.0 规则，不从多人旧草案读取参数：

```text
扣血 = m + floor(ln(max(x, 1)) × n)
```

其中 `m` 和 `n` 根据轮次使用冻结表。第一切片固定为第 1 轮，但接口仍接收 `round`。

## 11. 随机源、状态哈希和序列化

```csharp
public interface IDeterministicRandom
{
    int NextInt(int minInclusive, int maxExclusive);
    double NextDouble();
    void Shuffle<T>(IList<T> items);
    ulong State { get; }
}

public interface IStateHasher
{
    string Hash<T>(T state);
}

public interface IStateSerializer
{
    string Serialize<T>(T value);
    T Deserialize<T>(string json);
}
```

随机源必须由赛事种子创建，并在每次生成候选、洗牌和需要随机的规则事务中按固定顺序调用。不得调用 `System.Random.Shared`、Godot 全局随机源或时间作为规则随机数。

## 12. 视图投影和私有信息

完整 `MatchState` 只在规则核心内部使用。表现层和未来网络层读取投影：

```csharp
public interface IMatchViewProjector
{
    PublicMatchView CreatePublicView(MatchState state);
    PlayerMatchView CreatePlayerView(MatchState state, PlayerId viewer);
}

public sealed record PublicMatchView(
    int Round,
    MatchPhase Phase,
    IReadOnlyList<PublicPlayerInfo> Players,
    IReadOnlyList<PairingView> Pairings
);

public sealed record PlayerMatchView(
    PublicMatchView Public,
    PlayerId Viewer,
    DeckState OwnDeck,
    DraftState OwnDraft
);
```

当前阶段的本地单人模式可以显示全部四人的公开摘要，但不应让 UI 直接依赖其他玩家的私有 `DeckState`。这会避免未来改成联网模式时重新设计数据边界。

## 13. 赛事协调接口

```csharp
public interface IMatchCoordinator
{
    MatchState Start(StartMatchSetup setup);
    CommandResult<MatchState> Submit(IGameCommand command);
    CommandResult<MatchState> ApplyBattleResult(BattleResult result);
    CommandResult<MatchState> Submit(AdvanceSettlementCommand command);
    CommandResult<MatchState> Submit(BeginRoundDraftCommand command);
    MatchState CurrentState { get; }
    event Action<GameEvent>? EventProduced;
}

public sealed record StartMatchSetup(
    MatchId Match,
    int Seed,
    IReadOnlyList<PlayerSetup> Players
);

public sealed record PlayerSetup(
    PlayerId Id,
    PlayerKind Kind,
    string DisplayName
);
```

`MatchCoordinator` 的职责是：

- 校验赛事阶段和命令序号；
- 调用构筑、战斗和结算服务；
- 更新当前状态；
- 追加事件日志；
- 计算状态哈希；
- 通知表现层。

它不负责：

- 创建 Godot 节点；
- 播放动画；
- 选择 AI 行动；
- 直接解析 UI 按钮；
- 从网络连接读取字节流。

## 14. 第一切片的最小实现清单

必须实现：

- `CardDefinition`、`CardInstance`、`ICardDatabase`；
- `MatchState`、`PlayerState`、`DeckState`、`DraftState`、`CombatState`；
- `IGameCommand` 与第一切片命令；
- 基础 `GameEvent` 及事件序列；
- `IDeterministicRandom`；
- `IDraftEngine` 的基础购买流程；
- `ICombatEngine` 的基础战斗流程；
- `ITournamentDamageCalculator`；
- `IMatchCoordinator`；
- 固定配对服务；
- 一个确定性 AI 构筑策略和战斗策略；
- 固定种子 Headless 场景测试。

暂不实现：

- 完整共享池生成概率；
- 专精和路线状态转换；
- 混合元素传奇；
- 多轮淘汰和幽灵；
- 网络传输实现。

## 15. 失败处理约定

所有拒绝都返回结构化代码：

```text
WrongPhase
InvalidSequence
UnknownCard
OfferUnavailable
InsufficientStudyPoints
DuplicateCard
UnsupportedInSlice1
InvalidCombatAction
BattleAlreadyFinished
PlayerNotAuthorized
```

被拒绝的命令不能产生规则事件，不能消耗随机数，不能修改状态哈希。

## 16. 验收方式

接口草案进入实现前，需要确认以下行为：

1. 同一 `StartMatchSetup` 和种子产生相同初始状态。
2. 相同命令序列产生相同事件序列和状态哈希。
3. UI 和 AI 提交相同命令时，规则结果一致。
4. 非法命令不会改变状态或随机流。
5. 私有牌组不会出现在公共视图中。
6. 第一切片可以在没有 Godot 窗口的测试环境中完成完整赛事轮次。
7. 表现层只依赖事件和视图，不依赖规则内部实现类。

本草案通过后，再按“数据加载 → 状态模型 → 命令处理 → 构筑 → 战斗 → 赛事结算 → Godot 适配”的顺序创建 C# 文件。
