using System.Text.Json;
using System.Text.Json.Serialization;

namespace Magicians.Core.Cards;

public enum CardRarity
{
    Common,
    Rare,
    Epic,
    Legendary,
    Specialization
}

public enum CardKind
{
    Normal,
    Specialization,
    RouteLegendary,
    Legendary
}

public sealed record CardDefinition(
    string Name,
    int Cost,
    string Element,
    CardRarity Rarity,
    int Attack,
    int Defense,
    int Layers,
    bool Ability,
    CardKind Kind,
    string Text,
    string? RouteSupport
);

public sealed record CardFile(
    string Version,
    string Status,
    string Date,
    Dictionary<string, CardDefinition> Cards,
    Dictionary<string, object>? MechanicParameters = null,
    Dictionary<string, object>? RuntimeTables = null,
    string? Scope = null
);

public sealed record CardValidationIssue(string Code, string Message);

public sealed record CardValidationReport(
    bool IsValid,
    int CardCount,
    IReadOnlyList<CardValidationIssue> Issues
);

public sealed class FlexibleEnumConverter<TEnum> : JsonConverter<TEnum>
    where TEnum : struct, Enum
{
    public override TEnum Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
        var value = reader.GetString();
        if (string.IsNullOrWhiteSpace(value))
            throw new JsonException($"Empty value for {typeof(TEnum).Name}.");

        var normalized = Normalize(value);
        foreach (var name in Enum.GetNames<TEnum>())
        {
            if (Normalize(name).Equals(normalized, StringComparison.OrdinalIgnoreCase))
                return Enum.Parse<TEnum>(name);
        }

        throw new JsonException($"Unknown {typeof(TEnum).Name} value '{value}'.");
    }

    public override void Write(Utf8JsonWriter writer, TEnum value, JsonSerializerOptions options) =>
        writer.WriteStringValue(value.ToString());

    private static string Normalize(string value) =>
        value.Replace("_", string.Empty, StringComparison.Ordinal)
            .Replace("-", string.Empty, StringComparison.Ordinal)
            .Replace(" ", string.Empty, StringComparison.Ordinal);
}
