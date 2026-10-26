using Magicians.Core.Cards;
using Magicians.Core.Common;

namespace Magicians.Core.Match;

public sealed record DeckState(
    IReadOnlyList<CardInstance> Cards,
    IReadOnlyList<CardInstance> DrawPile,
    IReadOnlyList<CardInstance> DiscardPile,
    IReadOnlyList<CardInstance> ExhaustedCards
)
{
    public static DeckState CreateInitial(
        PlayerId owner,
        Slice1CardPool pool,
        IDeterministicRandom random)
    {
        var cards = new List<CardInstance>();
        foreach (var entry in pool.InitialDeck)
        {
            for (var index = 0; index < entry.Count; index++)
            {
                var instanceId = new CardInstanceId($"{owner.Value}:initial:{cards.Count:D2}");
                cards.Add(new CardInstance(instanceId, entry.CardId, owner));
            }
        }

        var drawPile = cards.ToList();
        random.Shuffle(drawPile);
        return new DeckState(
            Array.AsReadOnly(cards.ToArray()),
            Array.AsReadOnly(drawPile.ToArray()),
            Array.Empty<CardInstance>(),
            Array.Empty<CardInstance>());
    }
}
