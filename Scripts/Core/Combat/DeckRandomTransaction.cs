using Magicians.Core.Cards;

namespace Magicians.Core.Combat;

public sealed record DeckRandomTransaction(
    ulong RandomBefore,
    ulong RandomAfter,
    IReadOnlyList<CardInstance> InputDrawPile,
    IReadOnlyList<CardInstance> InputDiscardPile,
    IReadOnlyList<CardInstance> OutputDrawPile,
    IReadOnlyList<CardInstance> OutputDiscardPile
);
