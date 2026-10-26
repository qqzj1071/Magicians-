using System.Text.Json;

namespace Magicians.Core.Cards;

/// <summary>Art references are optional and independent from authoritative card rules.</summary>
public sealed record CardArtSlots(
    string IllustrationTexture = "",
    string FrameTexture = "",
    string ElementIconTexture = "",
    string EffectScene = "",
    string Sound = "");

public sealed record CardPresentationProfile(
    int SchemaVersion,
    string CardId,
    string ProfileId,
    string Name,
    string Element,
    string Rarity,
    int CombatCost,
    int BaseStudyCost,
    int Attack,
    int Defense,
    int FirstEnchantmentLayers,
    string RulesText,
    string DisplayRulesText,
    string[] RuleNotes,
    CardArtSlots Art);

/// <summary>One checked presentation profile per authoritative card. Profiles contain
/// readable snapshots for artists; stale rule copies fail validation rather than
/// silently changing what the player sees.</summary>
public sealed class CardPresentationCatalog
{
    private readonly IReadOnlyDictionary<string, CardPresentationProfile> _profiles;
    private CardPresentationCatalog(IReadOnlyDictionary<string, CardPresentationProfile> profiles) => _profiles = profiles;
    public IReadOnlyCollection<CardPresentationProfile> All => _profiles.Values.ToArray();
    public CardPresentationProfile Get(string cardId) => _profiles.TryGetValue(cardId, out var profile)
        ? profile : throw new KeyNotFoundException("No card presentation profile: " + cardId);

    public static CardPresentationCatalog Load(CardDatabase database, string directory)
    {
        var profiles = new Dictionary<string, CardPresentationProfile>(StringComparer.Ordinal);
        foreach (var path in Directory.EnumerateFiles(directory, "*.json").OrderBy(p => p, StringComparer.Ordinal))
        {
            var profile = JsonSerializer.Deserialize<CardPresentationProfile>(File.ReadAllText(path))
                ?? throw new InvalidDataException("Empty card presentation profile: " + path);
            var card = database.Get(profile.CardId);
            if (profile.SchemaVersion != 1 || string.IsNullOrWhiteSpace(profile.ProfileId) || profile.Name != card.Name ||
                profile.Element != card.Element || profile.Rarity != card.Rarity.ToString().ToLowerInvariant() ||
                profile.CombatCost != card.Cost || profile.Attack != card.Attack || profile.Defense != card.Defense ||
                profile.FirstEnchantmentLayers != card.Layers || profile.RulesText != card.Text ||
                profile.DisplayRulesText != EffectiveRulesText(card) ||
                profile.BaseStudyCost != StudyCost(card.Rarity) || profile.Art is null || profile.RuleNotes is null)
                throw new InvalidDataException("Stale card presentation profile; regenerate rule snapshots: " + path);
            if (!profiles.TryAdd(profile.CardId, profile))
                throw new InvalidDataException("Duplicate card presentation profile: " + profile.CardId);
        }
        if (profiles.Count != database.Count || profiles.Values.Select(p => p.ProfileId).Distinct().Count() != database.Count)
            throw new InvalidDataException("Card presentation profiles must cover every card exactly once with unique stable IDs.");
        return new(profiles);
    }

    public static int StudyCost(CardRarity rarity) => rarity switch
    { CardRarity.Common => 1, CardRarity.Rare => 2, CardRarity.Epic => 3, CardRarity.Legendary => 4, _ => 0 };

    // Keep the frozen source text for traceability, but display accepted rule corrections.
    public static string EffectiveRulesText(CardDefinition card) => card.Name switch
    {
        "焰心屏障" => "下一发主弹造成伤害前，获得本次有效攻击力50%的临时护盾。剩余临时护盾在获得后的下一个抽牌阶段前消失。",
        "临时壁垒" => "获得150临时护盾，本次不触发旧盾衰减。剩余临时护盾在获得后的下一个抽牌阶段前消失。",
        "岩潮壁垒" => "获得220临时护盾，本次不触发旧盾衰减。剩余临时护盾在获得后的下一个抽牌阶段前消失。",
        _ => card.Text
    };

    public static string ElementLabel(string element) => element switch
    { "fire" => "火", "water" => "水", "earth" => "土", "wind" => "风", "poison" => "毒", "generic" => "通用", _ => throw new InvalidDataException("Unknown card element: " + element) };
    public static string RarityLabel(string rarity) => rarity switch
    { "common" => "普通", "rare" => "稀有", "epic" => "史诗", "legendary" => "传奇", "specialization" => "专精", _ => throw new InvalidDataException("Unknown card rarity: " + rarity) };
}
