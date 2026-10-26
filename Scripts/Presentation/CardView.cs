using Godot;
using Magicians.Core.Cards;

namespace Magicians.Presentation;

/// <summary>Reusable card face; has no buying, combat or rules authority.</summary>
public partial class CardView : PanelContainer
{
    public void Bind(CardPresentationProfile profile, int? studyPrice = null, bool freePurchase = false, bool combat = false, bool enchantmentApplied = false)
    {
        GetNode<Label>("Margin/Column/Title").Text = profile.Name;
        var title = GetNode<Label>("Margin/Column/Title");
        title.AddThemeColorOverride("font_color", profile.FirstEnchantmentLayers > 0 && !enchantmentApplied
            ? new Color("ffd166") : Colors.White);
        GetNode<Label>("Margin/Column/Metadata").Text = $"元素：{CardPresentationCatalog.ElementLabel(profile.Element)}    稀有度：{CardPresentationCatalog.RarityLabel(profile.Rarity)}";
        GetNode<Label>("Margin/Column/Header/Element").Text = CardPresentationCatalog.ElementLabel(profile.Element);
        GetNode<Label>("Margin/Column/Header/Cost").Text = $"{profile.CombatCost} 费用";
        var rarity = GetNode<Label>("Margin/Column/Details/Text/StatsRarity/Rarity");
        rarity.Text = CardPresentationCatalog.RarityLabel(profile.Rarity);
        rarity.AddThemeColorOverride("font_color", RarityColor(profile.Rarity));
        GetNode<Label>("Margin/Column/Details/Text/StatsRarity/Attack").Text = $"攻击 +{profile.Attack}";
        GetNode<Label>("Margin/Column/Details/Text/StatsRarity/Defense").Text = $"防御 +{profile.Defense}";
        GetNode<Label>("Margin/Column/Details/Text/Enchantment").Text = profile.FirstEnchantmentLayers > 0
            ? enchantmentApplied
                ? $"附魔已叠加：{CardPresentationCatalog.ElementLabel(profile.Element)} +{profile.FirstEnchantmentLayers}层"
                : $"首次附魔：{CardPresentationCatalog.ElementLabel(profile.Element)} +{profile.FirstEnchantmentLayers}层（未叠加）"
            : "无附魔层";
        GetNode<Label>("Margin/Column/Details/Text/Rules").Text = FormatRulesText(profile.DisplayRulesText);
        var notes = GetNode<Label>("Margin/Column/Details/Text/RuleNotes");
        notes.Text = string.Join("\n", profile.RuleNotes);
        notes.Visible = profile.RuleNotes.Length > 0;
        GetNode<Label>("Margin/Column/Price").Text = profile.Rarity == "specialization" ? "专精赠牌（不出售）" : freePurchase
            ? $"本轮免费 · 原价{studyPrice ?? profile.BaseStudyCost}研习点"
            : $"购买：{studyPrice ?? profile.BaseStudyCost} 研习点";
        GetNode<Label>("Margin/Column/Price").Visible = !combat;
        var art = GetNode<ColorRect>("Margin/Column/Art");
        art.Color = ElementColor(profile.Element);
        BindTexture("Margin/Column/Art/Illustration", profile.Art.IllustrationTexture);
        BindTexture("Margin/Column/Art/Frame", profile.Art.FrameTexture);
        BindTexture("Margin/Column/Art/ElementIcon", profile.Art.ElementIconTexture);
        GetNode<Label>("Margin/Column/Art/Placeholder").Visible = string.IsNullOrEmpty(profile.Art.IllustrationTexture) ||
            !ResourceLoader.Exists(profile.Art.IllustrationTexture);
        SetMeta("card_id", profile.CardId);
        SetMeta("profile_id", profile.ProfileId);
    }

    private void BindTexture(string nodePath, string path)
    {
        var node = GetNode<TextureRect>(nodePath);
        node.Texture = !string.IsNullOrWhiteSpace(path) && ResourceLoader.Exists(path) ? GD.Load<Texture2D>(path) : null;
        node.Visible = node.Texture is not null;
    }

    public static string FormatRulesText(string text)
    {
        var timing = new[] { "立即", "整场", "下一发", "抽牌前", "下抽", "下一抽牌阶段前", "本次" };
        var result = text;
        foreach (var suffix in timing)
            if (result.EndsWith("；" + suffix, StringComparison.Ordinal))
                return result[..^(suffix.Length + 1)];
        return result;
    }

    private static Color ElementColor(string element) => element switch
    {
        "fire" => new Color("713b35"), "water" => new Color("284f73"),
        "earth" => new Color("655138"), "wind" => new Color("376258"),
        "poison" => new Color("5b3d72"), _ => new Color("464b57")
    };

    public static Color RarityColor(string rarity) => rarity switch
    {
        "common" => new Color("d6dce5"), "rare" => new Color("62b6ff"),
        "epic" => new Color("d295ff"), "legendary" => new Color("ffd166"),
        "specialization" => new Color("66dfbe"), _ => Colors.White
    };
}



