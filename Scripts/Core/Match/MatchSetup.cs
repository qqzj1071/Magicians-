using Magicians.Core.Common;

namespace Magicians.Core.Match;

public sealed record PlayerSetup(
    PlayerId Id,
    PlayerKind Kind,
    string DisplayName
);

public sealed record StartMatchSetup(
    MatchId Match,
    int Seed,
    IReadOnlyList<PlayerSetup> Players,
    int Round = 1,
    int InitialTournamentLife = 100,
    int InitialStudyPoints = 2,
    int OffersPerPlayer = 4,
    bool AllowRefresh = false,
    bool AllowRemove = false,
    bool AllowSpecialization = false,
    bool AllowRouteSelection = false
);
