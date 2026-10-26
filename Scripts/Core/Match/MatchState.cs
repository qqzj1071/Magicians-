using Magicians.Core.Common;

namespace Magicians.Core.Match;

public sealed record Pairing(
    BattleId BattleId,
    PlayerId PlayerA,
    PlayerId PlayerB
);

public sealed record BattleResult(
    BattleId Battle,
    PlayerId PlayerA,
    PlayerId PlayerB,
    PlayerId? Winner,
    int WinnerRemainingCombatLife,
    bool DoubleElimination
);

public sealed record RoundSummary(
    int Round,
    IReadOnlyList<Pairing> Pairings,
    IReadOnlyList<BattleResult> Results,
    IReadOnlyList<PlayerId> Survivors
);

public sealed record MatchState(
    MatchId Id,
    int Round,
    MatchPhase Phase,
    int Seed,
    ulong RandomState,
    int InitialStudyPoints,
    int OffersPerPlayer,
    bool AllowRefresh,
    bool AllowRemove,
    bool AllowSpecialization,
    bool AllowRouteSelection,
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
)
{
    public IReadOnlyDictionary<string, int> PendingPoolReturns { get; init; } = new Dictionary<string, int>(StringComparer.Ordinal);
    // Remaining physical legendary copies that have never been displayed this round.
    // Releasing an offer does not restore this budget; reset only at the next draft start.
    public IReadOnlyDictionary<string, int> UnseenLegendaryCopies { get; init; } = new Dictionary<string, int>(StringComparer.Ordinal);
}
