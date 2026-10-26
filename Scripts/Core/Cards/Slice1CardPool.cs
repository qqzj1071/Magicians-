using System.Text.Json;

namespace Magicians.Core.Cards;

public sealed record CardPoolEntry(string CardId, int Count);

public sealed record Slice1CardPool(
    string Id,
    string SourceVersion,
    IReadOnlyList<string> SupportedCardIds,
    IReadOnlyList<CardPoolEntry> InitialDeck,
    IReadOnlyList<CardPoolEntry> OfferPool,
    bool StarterCardsConsumePool = true
)
{
    public Magicians.Core.Draft.FrozenDraftRules? DraftRules { get; init; }
    public static Slice1CardPool Load(string path)
    {
        if (!File.Exists(path))
            throw new FileNotFoundException("Slice 1 card pool was not found.", path);
        var json = File.ReadAllText(path);
        return JsonSerializer.Deserialize<Slice1CardPool>(json, new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true
        }) ?? throw new InvalidDataException("Slice 1 card pool JSON was empty.");
    }

    public void ValidateAgainst(CardDatabase database)
    {
        if (!SourceVersion.Equals(database.Version, StringComparison.Ordinal))
            throw new InvalidDataException(
                $"Slice 1 pool version '{SourceVersion}' does not match card data version '{database.Version}'.");

        foreach (var cardId in SupportedCardIds)
            if (!database.TryGet(cardId, out _))
                throw new InvalidDataException($"Slice 1 card pool references unknown card '{cardId}'.");

        foreach (var entry in InitialDeck)
        {
            if (entry.Count <= 0)
                throw new InvalidDataException($"Initial deck count must be positive: '{entry.CardId}'.");
            if (!SupportedCardIds.Contains(entry.CardId, StringComparer.Ordinal))
                throw new InvalidDataException($"Initial deck card is not in the supported pool: '{entry.CardId}'.");
            if (!database.TryGet(entry.CardId, out _))
                throw new InvalidDataException($"Initial deck references unknown card '{entry.CardId}'.");

            var isAllowedDuplicate = entry.CardId is "攻击强化" or "防御强化";
            var maximum = isAllowedDuplicate ? 2 : 1;
            if (entry.Count > maximum)
                throw new InvalidDataException(
                    $"Initial deck violates v1.0 duplicate rule for '{entry.CardId}': maximum {maximum}.");
        }

        var initialIds = InitialDeck.Select(entry => entry.CardId).ToHashSet(StringComparer.Ordinal);
        var offerIds = new HashSet<string>(StringComparer.Ordinal);
        foreach (var entry in OfferPool)
        {
            if (entry.Count <= 0)
                throw new InvalidDataException($"Offer pool count must be positive: '{entry.CardId}'.");
            if (!SupportedCardIds.Contains(entry.CardId, StringComparer.Ordinal))
                throw new InvalidDataException($"Offer pool card is not in the supported pool: '{entry.CardId}'.");
            if (!offerIds.Add(entry.CardId))
                throw new InvalidDataException($"Offer pool contains duplicate card ID: '{entry.CardId}'.");
            if (StarterCardsConsumePool && initialIds.Contains(entry.CardId))
                throw new InvalidDataException($"Offer pool card is already in the initial deck: '{entry.CardId}'.");
            if (!database.TryGet(entry.CardId, out _))
                throw new InvalidDataException($"Offer pool references unknown card '{entry.CardId}'.");
        }
    }

    public static Slice1CardPool LoadFull(string poolCountsPath, string economyPath, CardDatabase database)
    {
        using var poolDocument = JsonDocument.Parse(File.ReadAllText(poolCountsPath));
        var cards = poolDocument.RootElement.GetProperty("cards");
        var offerPool = cards.EnumerateObject()
            .Select(property => new CardPoolEntry(property.Name, property.Value.GetProperty("copies").GetInt32()))
            .ToArray();

        using var economyDocument = JsonDocument.Parse(File.ReadAllText(economyPath));
        var starter = economyDocument.RootElement.GetProperty("starter")
            .EnumerateArray().Select(item => item.GetString()!).ToArray();
        var initial = starter.GroupBy(id => id, StringComparer.Ordinal)
            .Select(group => new CardPoolEntry(group.Key, group.Count())).ToArray();
        var supported = database.All.Select(card => card.Name).OrderBy(id => id, StringComparer.Ordinal).ToArray();
        var pool = new Slice1CardPool("frozen-v1.0-all-cards", database.Version, supported, initial, offerPool, false)
        { DraftRules = Magicians.Core.Draft.FrozenDraftRules.Load(Path.Combine(Path.GetDirectoryName(poolCountsPath)!, "probabilities.json")) };
        pool.ValidateAgainst(database);
        return pool;
    }
}
