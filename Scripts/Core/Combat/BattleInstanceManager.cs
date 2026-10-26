using Magicians.Core.Common;
using Magicians.Core.Cards;
using Magicians.Core.Match;

namespace Magicians.Core.Combat;

public sealed record BattleInstance(
    Pairing Pairing,
    CombatState State,
    DeckSnapshot SnapshotA,
    DeckSnapshot SnapshotB,
    int SeedA,
    int SeedB
);

public sealed class BattleInstanceManager
{
    private readonly ICombatEngine _engine;
    private readonly Dictionary<BattleId, BattleInstance> _instances = new();

    private BattleInstanceManager(ICombatEngine engine) => _engine = engine;

    public IReadOnlyDictionary<BattleId, BattleInstance> Instances => _instances;
    public ICombatEngine Engine => _engine;

    public IReadOnlyList<CardInstance> GetSearchCandidates(BattleId battle, PlayerId player) =>
        _engine.GetSearchCandidates(_instances[battle].State, player);

    public SearchSelectionSession? GetSearchSession(BattleId battle, PlayerId player, CardInstanceId sourceCard) =>
        _engine.GetSearchSession(_instances[battle].State, player, sourceCard);

    public static BattleInstanceManager Create(MatchState state, ICombatEngine engine)
    {
        if (state.Phase != MatchPhase.Combat)
            throw new InvalidOperationException("Battle instances require the combat phase.");
        var manager = new BattleInstanceManager(engine);
        var index = 0;
        foreach (var pairing in state.Pairings)
        {
            var playerA = state.Players[pairing.PlayerA];
            var playerB = state.Players[pairing.PlayerB];
            var ghostA = playerA.Kind == PlayerKind.Ghost;
            var ghostB = playerB.Kind == PlayerKind.Ghost;
            var setup = new CombatSetup(
                pairing.BattleId,
                new CombatantSetup(pairing.PlayerA, playerA.Deck.Cards.ToArray(), unchecked(state.Seed + (state.Round - 1) * 1000003 + index * 2 + 1)),
                new CombatantSetup(pairing.PlayerB, playerB.Deck.Cards.ToArray(), unchecked(state.Seed + (state.Round - 1) * 1000003 + index * 2 + 2)));
            var snapshotA = DeckSnapshot.Create(pairing.PlayerA, state.Round, setup.A.Cards);
            var snapshotB = DeckSnapshot.Create(pairing.PlayerB, state.Round, setup.B.Cards);
            var combatState = engine.Start(setup with
            {
                A = setup.A with { Cards = snapshotA.Cards },
                B = setup.B with { Cards = snapshotB.Cards }
            });

            manager._instances.Add(pairing.BattleId, new BattleInstance(
                pairing,
                combatState,
                snapshotA,
                snapshotB,
                setup.A.Seed,
                setup.B.Seed));
            index++;
        }
        return manager;
    }

    public CombatResolution Submit(CombatCommand command)
    {
        if (!_instances.TryGetValue(command.Battle, out var instance))
            throw new InvalidOperationException($"Unknown battle: {command.Battle}");
        var resolution = _engine.Submit(instance.State, command);
        if (resolution.Accepted)
            _instances[command.Battle] = instance with { State = resolution.State };
        return resolution;
    }

    public BattleResult GetResult(BattleId battle)
    {
        var instance = _instances[battle];
        if (instance.State.Phase != CombatPhase.Finished)
            throw new InvalidOperationException("Battle has not finished.");
        var winnerLife = instance.State.Winner == instance.State.A.Player
            ? instance.State.A.Life
            : instance.State.Winner == instance.State.B.Player ? instance.State.B.Life : 0;
        return new BattleResult(battle, instance.Pairing.PlayerA, instance.Pairing.PlayerB,
            instance.State.Winner, winnerLife, instance.State.DoubleKnockout);
    }
}

