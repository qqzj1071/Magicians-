using Magicians.Core.Common;
using Magicians.Core.Draft;
using Magicians.Core.Match;

namespace Magicians.Core.AI;

public enum DraftDecisionKind { Buy, Skip, Finish }
public sealed record DraftDecision(DraftDecisionKind Kind, string? OfferSlotId = null);
public sealed record DraftSelfObservation(PlayerId Id, int TournamentLife, DraftState Draft);
public sealed record DraftObservation
{
    public DraftSelfObservation Player { get; }
    public DraftObservation(PlayerState player) => Player = new(player.Id, player.TournamentLife, player.Draft with
    {
        Offers = player.Draft.Offers.ToArray(), PurchasedCardIds = player.Draft.PurchasedCardIds.ToArray(),
        ShownLegendaryIds = player.Draft.ShownLegendaryIds.ToArray()
    });
}

public interface IDraftPolicy
{
    DraftDecision Choose(DraftObservation observation);
}

public sealed class Slice1DraftPolicy : IDraftPolicy
{
    public int ReserveStudyPoints { get; }
    public int MinimumScore { get; }

    public Slice1DraftPolicy(int reserveStudyPoints = 1, int minimumScore = 60)
    {
        if (reserveStudyPoints < 0 || minimumScore < 0)
            throw new ArgumentOutOfRangeException();
        ReserveStudyPoints = reserveStudyPoints;
        MinimumScore = minimumScore;
    }

    public DraftDecision Choose(DraftObservation observation)
    {
        var affordable = observation.Player.Draft.Offers
            .Where(offer => !offer.IsResolved && offer.Cost <= observation.Player.Draft.StudyPoints)
            .OrderByDescending(Score)
            .ThenBy(offer => offer.SlotId, StringComparer.Ordinal)
            .FirstOrDefault();
        if (affordable is null)
            return new DraftDecision(DraftDecisionKind.Finish);

        var score = Score(affordable);
        var remaining = observation.Player.Draft.StudyPoints - affordable.Cost;
        return score < MinimumScore || remaining < ReserveStudyPoints
            ? new DraftDecision(DraftDecisionKind.Finish)
            : new DraftDecision(DraftDecisionKind.Buy, affordable.SlotId);
    }

    private static int Score(OfferSlot offer) => offer.Card.CardId switch
    {
        "护盾" or "石肤" => 100,
        "利刃" or "攻击强化" => 90,
        "防御强化" => 80,
        "速读" or "鼓舞" => 70,
        "微风" => 65,
        "水滴" => 60,
        _ => 0
    };
}
