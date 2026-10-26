namespace Magicians.Core.Common;

using Magicians.Core.Draft;
using Magicians.Core.Match;

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

public sealed record PlayerInitializedEvent(
    MatchId MatchId,
    int Round,
    long Sequence,
    string StateHash,
    PlayerId Player,
    PlayerKind Kind,
    int TournamentLife,
    int InitialDeckSize
) : GameEvent(MatchId, Round, Sequence, StateHash);

public sealed record DraftPhaseStartedEvent(
    MatchId MatchId,
    int Round,
    long Sequence,
    string StateHash,
    IReadOnlyList<PlayerId> Players
) : GameEvent(MatchId, Round, Sequence, StateHash);

public sealed record PairingsPublishedEvent(
    MatchId MatchId,
    int Round,
    long Sequence,
    string StateHash,
    IReadOnlyList<Pairing> Pairings
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

public sealed record RoundFinishedEvent(
    MatchId MatchId,
    int Round,
    long Sequence,
    string StateHash,
    IReadOnlyList<PlayerId> Survivors
) : GameEvent(MatchId, Round, Sequence, StateHash);

public sealed record SettlementStartedEvent(
    MatchId MatchId,
    int Round,
    long Sequence,
    string StateHash,
    IReadOnlyList<PlayerId> Survivors
) : GameEvent(MatchId, Round, Sequence, StateHash);

public sealed record NextRoundPreparedEvent(
    MatchId MatchId,
    int Round,
    long Sequence,
    string StateHash,
    IReadOnlyList<PlayerId> Participants
) : GameEvent(MatchId, Round, Sequence, StateHash);

public sealed record TournamentFinishedEvent(
    MatchId MatchId,
    int Round,
    long Sequence,
    string StateHash,
    IReadOnlyList<PlayerId> Champions
) : GameEvent(MatchId, Round, Sequence, StateHash);

public sealed record DraftRuleChangedEvent(
    MatchId MatchId,
    int Round,
    long Sequence,
    string StateHash,
    PlayerId Player,
    string Action,
    IReadOnlyList<string> CardIds
) : GameEvent(MatchId, Round, Sequence, StateHash);

public sealed record OffersGeneratedEvent(
    MatchId MatchId,
    int Round,
    long Sequence,
    string StateHash,
    PlayerId Owner,
    IReadOnlyList<OfferSlot> Offers
) : GameEvent(MatchId, Round, Sequence, StateHash);

public sealed record CardPurchasedEvent(
    MatchId MatchId,
    int Round,
    long Sequence,
    string StateHash,
    PlayerId Player,
    CardInstanceId Card,
    string OfferSlotId,
    int Cost
) : GameEvent(MatchId, Round, Sequence, StateHash);

public sealed record OfferSkippedEvent(
    MatchId MatchId,
    int Round,
    long Sequence,
    string StateHash,
    PlayerId Player,
    string OfferSlotId
) : GameEvent(MatchId, Round, Sequence, StateHash);

public sealed record DraftCompletedEvent(
    MatchId MatchId,
    int Round,
    long Sequence,
    string StateHash,
    PlayerId Player,
    int RemainingStudyPoints
) : GameEvent(MatchId, Round, Sequence, StateHash);

public sealed record DraftRoundCompletedEvent(
    MatchId MatchId,
    int Round,
    long Sequence,
    string StateHash,
    IReadOnlyList<PlayerId> Players
) : GameEvent(MatchId, Round, Sequence, StateHash);
