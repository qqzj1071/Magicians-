using Magicians.Core.Common;

namespace Magicians.Core.Match;

public sealed record TournamentPlacement(PlayerId Player, int Place, int RemainingLife, int? EliminatedRound, bool Champion);

public static class TournamentStandings
{
    public static IReadOnlyList<PlayerId> Champions(MatchState state)
    {
        if (state.Phase != MatchPhase.Finished) return Array.Empty<PlayerId>();
        var alive = state.Players.Values.Where(p => p.TournamentLife > 0).Select(p => p.Id).ToArray();
        if (alive.Length > 0) return alive;
        var lastRound = state.Players.Values.Max(p => p.EliminatedRound ?? state.Round);
        var finalPlayers = state.Players.Values.Where(p => p.EliminatedRound == lastRound).ToArray();
        var highestLife = finalPlayers.Max(p => p.TournamentLife);
        return finalPlayers.Where(p => p.TournamentLife == highestLife)
            .OrderBy(p => p.Id.Value, StringComparer.Ordinal).Select(p => p.Id).ToArray();
    }

    public static IReadOnlyList<TournamentPlacement> Calculate(MatchState state)
    {
        var champions = Champions(state).ToHashSet();
        var ordered = state.Players.Values.OrderByDescending(p => champions.Contains(p.Id))
            .ThenByDescending(p => p.TournamentLife > 0).ThenByDescending(p => p.EliminatedRound ?? int.MaxValue)
            .ThenByDescending(p => p.TournamentLife).ThenBy(p => p.Id.Value, StringComparer.Ordinal).ToArray();
        var output = new List<TournamentPlacement>();
        for (var i = 0; i < ordered.Length; i++)
        {
            var player = ordered[i];
            var tied = i > 0 && ((champions.Contains(player.Id) && champions.Contains(ordered[i - 1].Id)) ||
                (player.EliminatedRound == ordered[i - 1].EliminatedRound && player.TournamentLife == ordered[i - 1].TournamentLife));
            var place = tied ? output[^1].Place : i + 1;
            output.Add(new(player.Id, place, player.TournamentLife, player.EliminatedRound, champions.Contains(player.Id)));
        }
        return output;
    }
}
