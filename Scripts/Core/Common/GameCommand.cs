namespace Magicians.Core.Common;

public readonly record struct CommandSequence(long Value);

public interface IGameCommand
{
    MatchId MatchId { get; }
    PlayerId Issuer { get; }
    MatchPhase ExpectedPhase { get; }
    CommandSequence Sequence { get; }
}

public sealed record BeginDraftCommand(
    MatchId MatchId,
    PlayerId Issuer,
    CommandSequence Sequence
) : IGameCommand
{
    public MatchPhase ExpectedPhase => MatchPhase.Setup;
}

public sealed record BeginRoundDraftCommand(
    MatchId MatchId,
    PlayerId Issuer,
    CommandSequence Sequence
) : IGameCommand
{
    public MatchPhase ExpectedPhase => MatchPhase.Pairing;
}

public sealed record AdvanceSettlementCommand(
    MatchId MatchId,
    PlayerId Issuer,
    CommandSequence Sequence
) : IGameCommand
{
    public MatchPhase ExpectedPhase => MatchPhase.Settlement;
}

public sealed record RefreshOffersCommand(
    MatchId MatchId,
    PlayerId Issuer,
    CommandSequence Sequence
) : IGameCommand
{
    public MatchPhase ExpectedPhase => MatchPhase.Draft;
}

public sealed record RemoveCardCommand(
    MatchId MatchId,
    PlayerId Issuer,
    CardInstanceId Card,
    CommandSequence Sequence
) : IGameCommand
{
    public MatchPhase ExpectedPhase => MatchPhase.Draft;
}

public sealed record ChooseSpecializationCommand(
    MatchId MatchId,
    PlayerId Issuer,
    string Element,
    string CardId,
    CommandSequence Sequence
) : IGameCommand
{
    public MatchPhase ExpectedPhase => MatchPhase.Draft;
}

public sealed record ChooseRouteCommand(
    MatchId MatchId,
    PlayerId Issuer,
    string CardId,
    CommandSequence Sequence
) : IGameCommand
{
    public MatchPhase ExpectedPhase => MatchPhase.Draft;
}

public sealed record ReplaceRouteCommand(
    MatchId MatchId,
    PlayerId Issuer,
    string OldCardId,
    string NewCardId,
    CommandSequence Sequence
) : IGameCommand
{
    public MatchPhase ExpectedPhase => MatchPhase.Draft;
}

public sealed record BuyCardCommand(
    MatchId MatchId,
    PlayerId Issuer,
    string OfferSlotId,
    CommandSequence Sequence
) : IGameCommand
{
    public MatchPhase ExpectedPhase => MatchPhase.Draft;
    public CardInstanceId? ReplaceCard { get; init; }
}

public sealed record SkipOfferCommand(
    MatchId MatchId,
    PlayerId Issuer,
    string OfferSlotId,
    CommandSequence Sequence
) : IGameCommand
{
    public MatchPhase ExpectedPhase => MatchPhase.Draft;
}

public sealed record FinishDraftCommand(
    MatchId MatchId,
    PlayerId Issuer,
    CommandSequence Sequence
) : IGameCommand
{
    public MatchPhase ExpectedPhase => MatchPhase.Draft;
}
