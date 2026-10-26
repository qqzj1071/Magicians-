using Magicians.Core.Cards;

namespace Magicians.Core.Draft;

public sealed record OfferSlot(
    string SlotId,
    CardInstance Card,
    int Cost,
    bool IsPurchased = false,
    bool IsSkipped = false
)
{
    public bool IsResolved => IsPurchased || IsSkipped;
}

public sealed record DraftState(
    int Round,
    int StudyPoints,
    int RefreshesUsed,
    int RemovalCount,
    bool FreePurchaseUsed,
    string? SpecializationElement,
    string? RouteLegendaryId,
    IReadOnlyList<OfferSlot> Offers,
    IReadOnlyList<string> PurchasedCardIds,
    IReadOnlyList<string> ShownLegendaryIds,
    bool IsCompleted
)
{
    public IReadOnlyList<int> FirstRarities { get; init; } = Array.Empty<int>();
    public IReadOnlyList<int> RefreshRarities { get; init; } = Array.Empty<int>();
    public IReadOnlyList<string> AllocationAudit { get; init; } = Array.Empty<string>();
    public static DraftState Initial(int round, int studyPoints) => new(
        round,
        studyPoints,
        RefreshesUsed: 0,
        RemovalCount: 0,
        FreePurchaseUsed: false,
        SpecializationElement: null,
        RouteLegendaryId: null,
        Array.Empty<OfferSlot>(),
        Array.Empty<string>(),
        Array.Empty<string>(),
        IsCompleted: false);
}
