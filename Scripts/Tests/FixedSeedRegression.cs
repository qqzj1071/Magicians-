using Magicians.Core.AI;
using Magicians.Core.Cards;
using Magicians.Core.Combat;
using Magicians.Core.Common;
using Magicians.Core.Match;

namespace Magicians.Tests;

/// <summary>
/// Replays the slice-1 command path twice with the same seed. This deliberately
/// compares the observable state hash and battle snapshot instead of relying on
/// UI output, so it remains useful when the presentation layer is replaced.
/// </summary>
public static class FixedSeedRegression
{
    public const int Seed = 20261024;
    // 2026-10-26: draft templates/audit and unseen-copy budgets were added to the snapshot schema.
    public const string ExpectedFinalStateHash = "0b1106ddfd2e96408b26b850552480cd23ab0e4f2b049b9976791ce885124675";

    public static string Run(CardDatabase cards, Slice1CardPool pool, Slice1Scenario scenario)
    {
        var first = Replay(cards, pool, scenario);
        var second = Replay(cards, pool, scenario);
        if (!first.SequenceEqual(second, StringComparer.Ordinal))
            throw new InvalidDataException("Fixed-seed replay diverged between identical runs.");
        if (first[^1] != ExpectedFinalStateHash)
            throw new InvalidDataException($"Fixed-seed final hash changed: expected {ExpectedFinalStateHash}, got {first[^1]}.");
        return first[^1];
    }

    private static IReadOnlyList<string> Replay(CardDatabase cards, Slice1CardPool pool, Slice1Scenario scenario)
    {
        var coordinator = new MatchCoordinator(cards, pool);
        var state = coordinator.Start(new StartMatchSetup(
            new MatchId("fixed-seed-regression"), Seed, Participants(), scenario.Round,
            scenario.InitialTournamentLife, scenario.InitialStudyPoints, scenario.OffersPerPlayer));
        var hashes = new List<string> { StateHasher.Hash(state) };

        Accept(coordinator, new BeginDraftCommand(state.Id, new PlayerId("human"), Next(coordinator)), hashes);
        var policies = new Dictionary<PlayerId, Slice1AiController>
        {
            [new PlayerId("ai-1")] = new(new Slice1DraftPolicy(0, 60)),
            [new PlayerId("ai-2")] = new(new Slice1DraftPolicy(1, 60)),
            [new PlayerId("ai-3")] = new(new Slice1DraftPolicy(1, 85))
        };
        foreach (var player in Participants().OrderBy(item => item.Id.Value, StringComparer.Ordinal))
        {
            if (player.Kind == PlayerKind.Ai)
            {
                policies[player.Id].CompleteDraft(coordinator, player.Id);
                hashes.Add(StateHasher.Hash(coordinator.CurrentState));
                continue;
            }

            var human = coordinator.CurrentState.Players[player.Id];
            var offer = human.Draft.Offers[0];
            Accept(coordinator, new BuyCardCommand(coordinator.CurrentState.Id, player.Id, offer.SlotId, Next(coordinator)), hashes);
            Accept(coordinator, new FinishDraftCommand(coordinator.CurrentState.Id, player.Id, Next(coordinator)), hashes);
        }

        var completed = coordinator.CurrentState;
        var manager = BattleInstanceManager.Create(completed, new Slice1CombatEngine(cards));
        foreach (var instance in manager.Instances.Values.OrderBy(item => item.Pairing.BattleId.Value, StringComparer.Ordinal))
            hashes.Add(CombatSignature(instance.State));

        foreach (var pairing in completed.Pairings)
        {
            var result = new BattleResult(pairing.BattleId, pairing.PlayerA, pairing.PlayerB,
                pairing.PlayerA, 900, false);
            var applied = coordinator.ApplyBattleResult(result);
            if (!applied.Accepted)
                throw new InvalidDataException($"Fixed-seed settlement rejected: {applied.Rejection?.Code}");
            hashes.Add(StateHasher.Hash(coordinator.CurrentState));
        }
        Accept(coordinator, new AdvanceSettlementCommand(
            coordinator.CurrentState.Id, new PlayerId("human"), Next(coordinator)), hashes);
        Accept(coordinator, new BeginRoundDraftCommand(
            coordinator.CurrentState.Id, new PlayerId("human"), Next(coordinator)), hashes);
        return hashes;
    }

    private static void Accept(MatchCoordinator coordinator, IGameCommand command, ICollection<string> hashes)
    {
        var result = coordinator.Submit(command);
        if (!result.Accepted)
            throw new InvalidDataException($"Fixed-seed command rejected: {result.Rejection?.Code}");
        hashes.Add(StateHasher.Hash(result.State));
    }

    private static CommandSequence Next(MatchCoordinator coordinator) =>
        new(coordinator.CurrentState.EventSequence + 1);

    private static string CombatSignature(CombatState state) => string.Join("|",
        state.Battle.Value, state.A.Player.Value, state.Revision, state.A.RandomState,
        string.Join(',', state.A.CurrentPool.Select(card => card.CardId)),
        state.B.Player.Value, state.B.RandomState,
        string.Join(',', state.B.CurrentPool.Select(card => card.CardId)));

    private static IReadOnlyList<PlayerSetup> Participants() => new[]
    {
        new PlayerSetup(new PlayerId("human"), PlayerKind.Human, "Player"),
        new PlayerSetup(new PlayerId("ai-1"), PlayerKind.Ai, "AI 1"),
        new PlayerSetup(new PlayerId("ai-2"), PlayerKind.Ai, "AI 2"),
        new PlayerSetup(new PlayerId("ai-3"), PlayerKind.Ai, "AI 3")
    };
}


