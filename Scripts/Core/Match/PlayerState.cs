using Magicians.Core.Common;
using Magicians.Core.Draft;

namespace Magicians.Core.Match;

public sealed record PublicPlayerInfo(
    string DisplayName,
    bool IsEliminated = false
);

public sealed record PlayerState(
    PlayerId Id,
    PlayerKind Kind,
    int TournamentLife,
    DeckState Deck,
    DraftState Draft,
    PublicPlayerInfo PublicInfo,
    int WinStreak = 0,
    int LossStreak = 0,
    int? EliminatedRound = null
);
