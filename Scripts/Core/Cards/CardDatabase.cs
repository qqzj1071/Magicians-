using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Magicians.Core.Cards;

public sealed class CardDatabase
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        ReadCommentHandling = JsonCommentHandling.Skip,
        AllowTrailingCommas = true,
        Converters =
        {
            new FlexibleEnumConverter<CardRarity>(),
            new FlexibleEnumConverter<CardKind>()
        }
    };

    private readonly CardFile _file;
    private readonly IReadOnlyDictionary<string, CardDefinition> _cards;

    private CardDatabase(CardFile file)
    {
        _file = file;
        _cards = file.Cards;
    }

    public string Version => _file.Version;
    public int Count => _cards.Count;
    public IEnumerable<CardDefinition> All => _cards.Values;

    public CardDefinition Get(string cardId)
    {
        if (!_cards.TryGetValue(cardId, out var card))
            throw new KeyNotFoundException($"Unknown card: {cardId}");
        return card;
    }

    public bool TryGet(string cardId, out CardDefinition card) =>
        _cards.TryGetValue(cardId, out card!);

    public static CardDatabase LoadFromJson(string path, string? expectedSha256 = null)
    {
        if (!File.Exists(path))
            throw new FileNotFoundException("Card data file was not found.", path);

        if (!string.IsNullOrWhiteSpace(expectedSha256))
        {
            var actualSha256 = ComputeSha256(path);
            if (!actualSha256.Equals(expectedSha256, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException($"Card data hash mismatch. Expected {expectedSha256}, got {actualSha256}.");
        }

        var json = File.ReadAllText(path);
        var file = JsonSerializer.Deserialize<CardFile>(json, JsonOptions)
            ?? throw new InvalidDataException("Card data JSON was empty.");
        var report = Validate(file);
        if (!report.IsValid)
        {
            var details = string.Join(Environment.NewLine,
                report.Issues.Select(issue => $"[{issue.Code}] {issue.Message}"));
            throw new InvalidDataException($"Card data validation failed:{Environment.NewLine}{details}");
        }
        return new CardDatabase(file);
    }

    public static CardValidationReport Validate(CardFile? file)
    {
        var issues = new List<CardValidationIssue>();
        if (file is null)
        {
            issues.Add(new("MissingDocument", "Card document is null."));
            return new(false, 0, issues);
        }
        if (string.IsNullOrWhiteSpace(file.Version))
            issues.Add(new("MissingVersion", "The top-level version is required."));
        if (file.Cards is null || file.Cards.Count == 0)
            issues.Add(new("MissingCards", "The cards object must contain at least one card."));

        foreach (var entry in file.Cards ?? new Dictionary<string, CardDefinition>())
        {
            var id = entry.Key;
            var card = entry.Value;
            if (card is null)
            {
                issues.Add(new("NullCard", $"Card '{id}' is null."));
                continue;
            }
            if (!id.Equals(card.Name, StringComparison.Ordinal))
                issues.Add(new("IdNameMismatch", $"Card key '{id}' does not match name '{card.Name}'."));
            if (card.Cost < 0)
                issues.Add(new("NegativeCost", $"Card '{id}' has a negative cost."));
            if (card.Attack < 0 || card.Defense < 0 || card.Layers < 0)
                issues.Add(new("NegativeStats", $"Card '{id}' has negative attack, defense, or layers."));
            if (string.IsNullOrWhiteSpace(card.Element))
                issues.Add(new("MissingElement", $"Card '{id}' has no element."));
            if (string.IsNullOrWhiteSpace(card.Text))
                issues.Add(new("MissingText", $"Card '{id}' has no rules text."));
        }
        return new(issues.Count == 0, file.Cards?.Count ?? 0, issues);
    }

    private static string ComputeSha256(string path)
    {
        using var stream = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }
}
