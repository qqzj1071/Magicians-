using Magicians.Core.Common;

namespace Magicians.Core.Match;

public interface ITournamentDamageCalculator
{
    int CalculateLoss(int round, int winnerRemainingCombatLife);
    int CalculateDoubleEliminationLoss(int round);
}

public sealed class FrozenV1TournamentDamageCalculator : ITournamentDamageCalculator
{
    public int CalculateLoss(int round, int winnerRemainingCombatLife)
    {
        var (m, n) = Parameters(round);
        return m + (int)Math.Floor(Math.Log(Math.Max(winnerRemainingCombatLife, 1)) * n);
    }

    public int CalculateDoubleEliminationLoss(int round) => Parameters(round).m;

    private static (int m, double n) Parameters(int round) => round switch
    {
        <= 4 => (2, 0.8),
        <= 8 => (4, 1.8),
        <= 12 => (7, 2.0),
        <= 14 => (9, 3.2),
        <= 16 => (10, 4.5),
        _ => (11, 6.0)
    };
}

public sealed record SettlementResult(
    MatchState State,
    IReadOnlyList<GameEvent> Events
);
