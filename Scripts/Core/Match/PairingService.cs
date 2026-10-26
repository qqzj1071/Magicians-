using Magicians.Core.Common;

namespace Magicians.Core.Match;

public interface IPairingService
{
    IReadOnlyList<Pairing> CreateFirstRound(IReadOnlyDictionary<PlayerId, PlayerState> players);
    IReadOnlyList<Pairing> CreateNextRound(
        IReadOnlyDictionary<PlayerId, PlayerState> players,
        IReadOnlyList<Pairing> pairingHistory,
        int round);
}

public sealed class FirstRoundPairingService : IPairingService
{
    public IReadOnlyList<Pairing> CreateFirstRound(IReadOnlyDictionary<PlayerId, PlayerState> players)
    {
        var human = players.Values.Single(player => player.Kind == PlayerKind.Human);
        var ai = players.Values.Where(player => player.Kind == PlayerKind.Ai)
            .OrderBy(player => player.Id.Value, StringComparer.Ordinal).ToArray();
        if (ai.Length != 3)
            throw new InvalidOperationException("First round requires three AI players.");

        return new[]
        {
            new Pairing(new BattleId("battle-1"), human.Id, ai[0].Id),
            new Pairing(new BattleId("battle-2"), ai[1].Id, ai[2].Id)
        };
    }

    public IReadOnlyList<Pairing> CreateNextRound(
        IReadOnlyDictionary<PlayerId, PlayerState> players,
        IReadOnlyList<Pairing> pairingHistory,
        int round)
    {
        var participants = players.Values
            .Where(player => player.TournamentLife > 0)
            .OrderBy(player => player.Id.Value, StringComparer.Ordinal)
            .ToList();
        if (participants.Count < 2)
            throw new InvalidOperationException("The next round requires at least two surviving participants.");
        if (participants.Count % 2 != 0)
        {
            var ghost = players.Values
                .Where(player => player.Kind == PlayerKind.Ghost)
                .OrderBy(player => player.Id.Value, StringComparer.Ordinal)
                .FirstOrDefault();
            if (ghost is null)
                throw new InvalidOperationException("An odd number of survivors requires an available ghost snapshot.");
            participants.Add(ghost);
        }

        var layouts = participants.Count == 2
            ? new[] { new[] { 0, 1 } }
            : new[] { new[] { 0, 1, 2, 3 }, new[] { 0, 2, 1, 3 }, new[] { 0, 3, 1, 2 } };
        bool Same(Pairing pairing, PlayerId a, PlayerId b) =>
            pairing.PlayerA == a && pairing.PlayerB == b || pairing.PlayerA == b && pairing.PlayerB == a;
        var recent = pairingHistory.Where(p => round == 2
            ? p.BattleId.Value.StartsWith("battle-", StringComparison.Ordinal)
            : p.BattleId.Value.StartsWith($"round-{round - 1}-", StringComparison.Ordinal)).ToArray();
        int Repeats(int[] layout, IEnumerable<Pairing> history) => Enumerable.Range(0, layout.Length / 2)
            .Sum(i => history.Count(p => Same(p, participants[layout[i * 2]].Id, participants[layout[i * 2 + 1]].Id)));
        var selected = layouts.OrderBy(layout => Repeats(layout, recent))
            .ThenBy(layout => Repeats(layout, pairingHistory)).First();
        return Enumerable.Range(0, selected.Length / 2).Select(i => new Pairing(
            new BattleId($"round-{round}-battle-{i + 1}"), participants[selected[i * 2]].Id,
            participants[selected[i * 2 + 1]].Id)).ToArray();
    }
}

