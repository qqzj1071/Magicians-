using Magicians.Core.Cards;
using Magicians.Core.Common;
using Magicians.Core.Combat;
using Magicians.Core.Match;
using Magicians.Core.AI;
using System.Security.Cryptography;

namespace Magicians.Application;

public sealed class GameSession : IDisposable
{
    public static GameSession? Current { get; set; }

    public CardDatabase Cards { get; }
    public CardPresentationCatalog CardProfiles { get; }
    public Slice1CardPool CardPool { get; }
    public Slice1CardPool FullCardPool { get; }
    public Slice1Scenario Scenario { get; }
    public MatchCoordinator Coordinator { get; }
    public BattleInstanceManager? BattleInstances { get; private set; }
    private int _battleRound;
    private int? _delegatedCombatRound;
    public bool IsHumanCombatDelegated => _delegatedCombatRound == Coordinator.CurrentState.Round;
    public BattleInstance? HumanBattle => BattleInstances?.Instances.Values.FirstOrDefault(i =>
        i.Pairing.PlayerA.Value == "human" || i.Pairing.PlayerB.Value == "human");
    public TrainedAiRuntime Ai { get; }
    public string? AiError { get; private set; }
    private readonly List<BattleResultAnnouncement> _battleAnnouncements = new();
    public IReadOnlyList<BattleResultAnnouncement> BattleAnnouncements => _battleAnnouncements;
    private readonly Dictionary<(int Round, BattleId Battle), RecordedBattle> _recordedBattles = new();
    public IReadOnlyList<RecordedBattle> RecordedBattles => _recordedBattles.Values.OrderBy(b => b.Round)
        .ThenBy(b => b.Pairing.BattleId.Value, StringComparer.Ordinal).ToArray();
    private readonly Dictionary<PlayerId, (long Sequence, Task<AiLegalDraftAction> Task)> _draftTasks = new();
    private readonly Dictionary<(BattleId, PlayerId), (long Revision, Task<CombatAction> Task)> _combatTasks = new();

    private GameSession(string root, CardDatabase cards, CardPresentationCatalog profiles, Slice1CardPool pool, Slice1CardPool fullPool, Slice1Scenario scenario, MatchCoordinator coordinator)
    {
        Ai = new TrainedAiRuntime(root);
        Cards = cards;
        CardProfiles = profiles;
        CardPool = pool;
        FullCardPool = fullPool;
        Scenario = scenario;
        Coordinator = coordinator;
    }

    public static GameSession CreateSlice1(string projectRoot, int? seed = null)
        => CreateSession(projectRoot, seed ?? RandomNumberGenerator.GetInt32(1, int.MaxValue), null);

    internal static GameSession CreateScenario(string projectRoot, Slice1Scenario scenario, int seed = 20261024)
        => CreateSession(projectRoot, seed, scenario);

    private static GameSession CreateSession(string projectRoot, int seed, Slice1Scenario? scenarioOverride)
    {
        var cards = CardDatabase.LoadFromJson(Path.Combine(projectRoot, "releases", "v1.0", "cards.json"));
        var profiles = CardPresentationCatalog.Load(cards, Path.Combine(projectRoot, "Data", "Presentation", "Cards"));
        var pool = Slice1CardPool.Load(Path.Combine(projectRoot, "Data", "slice1", "slice1-card-pool.json"));
        var fullPool = Slice1CardPool.LoadFull(
            Path.Combine(projectRoot, "releases", "deckbuilding-v1.0", "pool-counts.json"),
            Path.Combine(projectRoot, "releases", "deckbuilding-v1.0", "economy.json"),
            cards);
        var scenario = scenarioOverride ?? Slice1Scenario.Load(Path.Combine(projectRoot, "Data", "slice1", "scenario.json"));
        pool.ValidateAgainst(cards);
        FullPoolActivationGuard.RequireAllEffectsImplemented(fullPool, CardEffectRegistry.CreateSlice1(cards));
        pool = fullPool;
        var coordinator = new MatchCoordinator(cards, pool);
        coordinator.Start(new StartMatchSetup(
            new MatchId("local-slice1"),
            seed,
            new[]
            {
                new PlayerSetup(new PlayerId("human"), PlayerKind.Human, "Player"),
                new PlayerSetup(new PlayerId("ai-1"), PlayerKind.Ai, "AI 1"),
                new PlayerSetup(new PlayerId("ai-2"), PlayerKind.Ai, "AI 2"),
                new PlayerSetup(new PlayerId("ai-3"), PlayerKind.Ai, "AI 3")
            },
            scenario.Round,
            scenario.InitialTournamentLife,
            scenario.InitialStudyPoints,
            8,
            scenario.AllowRefresh,
            scenario.AllowRemove,
            scenario.AllowSpecialization,
            scenario.AllowRouteSelection));
        return new GameSession(projectRoot, cards, profiles, pool, fullPool, scenario, coordinator);
    }

    public void BeginDraft()
    {
        var state = Coordinator.CurrentState;
        if (state.Phase != MatchPhase.Setup)
            return;
        var result = Coordinator.Submit(new BeginDraftCommand(
            state.Id,
            new PlayerId("human"),
            new CommandSequence(state.EventSequence + 1)));
        if (!result.Accepted)
            throw new InvalidOperationException(result.Rejection?.Message);
    }

    /// <summary>
    /// Creates the deterministic battle snapshot once the coordinator enters combat.
    /// The manager is retained through settlement so the presentation layer can show
    /// the final combat state without rebuilding or rerolling either deck.
    /// </summary>
    public BattleInstanceManager EnsureBattleInstances()
    {
        if (BattleInstances is not null && _battleRound == Coordinator.CurrentState.Round)
            return BattleInstances;
        var state = Coordinator.CurrentState;
        if (state.Phase is not (MatchPhase.Combat or MatchPhase.Finished))
            throw new InvalidOperationException("Battle instances are unavailable before combat.");
        BattleInstances = BattleInstanceManager.Create(
            state with { Phase = MatchPhase.Combat },
            new Slice1CombatEngine(Cards));
        _battleRound = state.Round;
        foreach (var battle in BattleInstances.Instances.Values)
            _recordedBattles.TryAdd((state.Round, battle.Pairing.BattleId), new RecordedBattle(state.Round, battle.Pairing));
        return BattleInstances;
    }

    public bool DelegateHumanCombat()
    {
        if (Coordinator.CurrentState.Phase != MatchPhase.Combat) return false;
        EnsureBattleInstances();
        if (HumanBattle is not { State.Phase: not CombatPhase.Finished }) return false;
        _delegatedCombatRound = Coordinator.CurrentState.Round;
        return true;
    }

    public CombatResolution SubmitCombat(CombatCommand command)
    {
        var manager = EnsureBattleInstances();
        if (command.Player.Value == "human" && IsHumanCombatDelegated)
            return new(false, manager.Instances[command.Battle].State, Array.Empty<CombatEvent>(),
                new Rejection("CombatDelegated", "本轮战斗已由AI代理。"));
        return ExecuteCombat(command);
    }

    private CombatResolution ExecuteCombat(CombatCommand command)
    {
        var resolution = EnsureBattleInstances().Submit(command);
        if (resolution.Accepted)
            _recordedBattles[(Coordinator.CurrentState.Round, command.Battle)].Append(resolution.Events);
        return resolution;
    }

    public CommandResult<MatchState> ApplyFinishedBattle(BattleId battle)
    {
        var manager = EnsureBattleInstances();
        var result = manager.GetResult(battle);
        var applied = Coordinator.ApplyBattleResult(result);
        if (applied.Accepted)
        {
            _battleAnnouncements.Add(BattleResultAnnouncement.Create(result, applied.State, applied.Events));
            _recordedBattles[(applied.State.Round, battle)].Result = result;
        }
        return applied;
    }

    public void CompleteAiDrafts()
    {
        foreach (var player in Coordinator.CurrentState.Players.Values.Where(p => p.TournamentLife > 0 && p.Kind == PlayerKind.Ai).ToArray())
            CompleteDraftFor(player.Id);
    }

    public void AdvanceRound()
    {
        var state = Coordinator.CurrentState;
        if (state.Phase != MatchPhase.Settlement) return;
        var issuer = new PlayerId("human");
        var result = Coordinator.Submit(new AdvanceSettlementCommand(state.Id, issuer, new(state.EventSequence + 1)));
        if (!result.Accepted) throw new InvalidOperationException(result.Rejection?.Message);
        if (result.State.Phase == MatchPhase.Finished) return;
        BattleInstances = null;
        _delegatedCombatRound = null;
        _combatTasks.Clear();
        state = Coordinator.CurrentState;
        result = Coordinator.Submit(new BeginRoundDraftCommand(state.Id, issuer, new(state.EventSequence + 1)));
        if (!result.Accepted) throw new InvalidOperationException(result.Rejection?.Message);

    }

    public void CompleteDraftFor(PlayerId player)
    {
        for (var step = 0; step < 64; step++)
        {
            var state = Coordinator.CurrentState;
            if (state.Phase != MatchPhase.Draft || state.Players[player].Draft.IsCompleted || state.Players[player].TournamentLife <= 0) return;
            var action = DiversifyDraftAction(state, player, Ai.ChooseDraft(AiObservations.Draft(state, player, Cards)));
            var result = Coordinator.Submit(TrainedAiRuntime.DraftCommand(state, player, action));
            if (!result.Accepted) throw new InvalidOperationException("Trained draft command rejected: " + result.Rejection?.Code);
        }
        throw new InvalidOperationException("Trained draft exceeded its bounded action count.");
    }

    private AiLegalDraftAction DiversifyDraftAction(MatchState state, PlayerId player, AiLegalDraftAction action)
    {
        if (action.Kind != "buy" || action.Card is null || state.Players[player].Kind != PlayerKind.Ai) return action;
        var otherAiChoices = state.Players.Values.Where(p => p.Kind == PlayerKind.Ai && p.Id != player)
            .SelectMany(p => p.Draft.PurchasedCardIds).ToHashSet(StringComparer.Ordinal);
        if (!otherAiChoices.Contains(action.Card)) return action;
        var alternatives = AiObservations.Draft(state, player, Cards).LegalActions
            .Where(a => a.Kind == "buy" && a.Card is not null && !otherAiChoices.Contains(a.Card))
            .OrderBy(a => Cards.Get(a.Card!).Kind == CardKind.RouteLegendary ? 0 : 1)
            .ThenBy(a => a.Card, StringComparer.Ordinal).ToArray();
        return alternatives.FirstOrDefault() ?? action;
    }

    public CombatAction ChooseAutomaticAction(BattleInstance instance, PlayerId player)
    {
        var observation = AiObservations.Combat(Coordinator.CurrentState, instance, player);
        return DecideCombat(observation, instance, player);
    }

    private CombatAction DecideCombat(AiCombatView observation, BattleInstance instance, PlayerId player)
    {
        var action = Ai.ChooseCombat(observation);
        if (action.Kind == CombatActionKind.PlayCard && action.Card is { } card &&
            new Slice1CombatEngine(Cards).GetSearchSession(instance.State, player, card) is { } search)
            action = Ai.ChooseSearch(action, search, observation);
        return action;
    }

    // Only completed decisions are applied on the Godot thread. Python inference
    // is serialized per participant, never blocks a UI frame, and cannot mutate authority.
    public IReadOnlyList<CombatEvent> TickAutonomous(int budget = 8)
    {
        if (AiError is not null) return Array.Empty<CombatEvent>();
        try { return TickAi(budget); }
        catch (Exception error) { AiError = error.Message; throw; }
    }

    private IReadOnlyList<CombatEvent> TickAi(int budget)
    {
        var events = new List<CombatEvent>();
        var match = Coordinator.CurrentState;
        if (match.Phase == MatchPhase.Draft)
        {
            foreach (var player in match.Players.Values.Where(p => p.Kind == PlayerKind.Ai && p.TournamentLife > 0 && !p.Draft.IsCompleted))
            {
                if (!_draftTasks.TryGetValue(player.Id, out var pending))
                {
                    var view = AiObservations.Draft(match, player.Id, Cards);
                    _draftTasks[player.Id] = (match.EventSequence, Task.Run(() => Ai.ChooseDraft(view)));
                    break;
                }
                if (!pending.Task.IsCompleted) break;
                _draftTasks.Remove(player.Id);
                var decision = pending.Task.GetAwaiter().GetResult();
                if (pending.Sequence != Coordinator.CurrentState.EventSequence) break;
                var result = Coordinator.Submit(TrainedAiRuntime.DraftCommand(match, player.Id, decision));
                if (!result.Accepted) throw new InvalidOperationException("Trained draft rejected: " + result.Rejection?.Code);
                break;
            }
            return events;
        }
        if (match.Phase != MatchPhase.Combat) return events;
        var manager = EnsureBattleInstances();
        foreach (var id in manager.Instances.Values
                     .OrderByDescending(i => i.Pairing.PlayerA.Value == "human" || i.Pairing.PlayerB.Value == "human")
                     .Select(i => i.Pairing.BattleId).ToArray())
        {
            for (var step = 0; step < budget; step++)
            {
                var instance = manager.Instances[id];
                if (instance.State.Phase == CombatPhase.Finished) break;
                var next = new[] { instance.State.A.Player, instance.State.B.Player }
                    .Where(p => !instance.State.EndedWindows.Contains(p) && !instance.State.PendingActions.Any(a => a.Player == p))
                    .Where(p => p.Value != "human" || match.Players[p].Kind != PlayerKind.Human || IsHumanCombatDelegated).ToArray();
                if (next.Length == 0) break;
                var key = (id, next[0]);
                if (!_combatTasks.TryGetValue(key, out var pending))
                {
                    var view = AiObservations.Combat(match, instance, next[0]);
                    var actor = next[0];
                    _combatTasks[key] = (instance.State.Revision, Task.Run(() => DecideCombat(view, instance, actor)));
                    break;
                }
                if (!pending.Task.IsCompleted) break;
                _combatTasks.Remove(key);
                var action = pending.Task.GetAwaiter().GetResult();
                if (pending.Revision != instance.State.Revision) break;
                var resolution = ExecuteCombat(new CombatCommand(id, next[0], pending.Revision, action));
                if (!resolution.Accepted) throw new InvalidOperationException("Trained combat rejected: " + resolution.Rejection?.Code);
                events.AddRange(CombatPlayerView.VisibleEvents(instance, new PlayerId("human"), resolution.Events));
            }
            if (manager.Instances[id].State.Phase == CombatPhase.Finished && !Coordinator.CurrentState.BattleResults.Any(r => r.Battle == id))
            {
                var result = ApplyFinishedBattle(id);
                if (!result.Accepted) throw new InvalidOperationException(result.Rejection?.Message);
            }
        }
        return events;
    }

    public void Dispose() => Ai.Dispose();
}
