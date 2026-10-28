using Godot;
using System.Text.Json;
using Magicians.Core.Cards;
using Magicians.Core.Combat;
using Magicians.Core.Common;
using Magicians.Presentation;

namespace Magicians.Tests;

public static class CardPresentationRegression
{
    public static void Run(CardDatabase database, string root)
    {
        var catalog = CardPresentationCatalog.Load(database, Path.Combine(root, "Data", "Presentation", "Cards"));
        using var creative = JsonDocument.Parse(File.ReadAllText(Path.Combine(root, "Data", "Creative", "fire-flavor-texts.zh-CN.json")));
        if (creative.RootElement.GetProperty("ShowInMatchUi").GetBoolean())
            throw new InvalidDataException("Flavor text must remain disabled in the match UI.");
        var creativeCards = creative.RootElement.GetProperty("Cards").EnumerateArray().ToArray();
        var fireIds = database.All.Where(card => card.Element == "fire").Select(card => card.Name).ToHashSet(StringComparer.Ordinal);
        if (creativeCards.Length != fireIds.Count ||
            !creativeCards.Select(card => card.GetProperty("CardId").GetString()!).ToHashSet(StringComparer.Ordinal).SetEquals(fireIds))
            throw new InvalidDataException("The creative archive must retain every fire card exactly once.");
        var flavorTexts = creativeCards.Select(c => c.GetProperty("FlavorText").GetString()!).ToArray();
        foreach (var entry in creativeCards)
        {
            var id = entry.GetProperty("CardId").GetString()!;
            var profile = catalog.Get(id);
            if (catalog.NameFor(id) != entry.GetProperty("DisplayName").GetString() ||
                profile.ProfileId != entry.GetProperty("ProfileId").GetString() || database.Get(id).Name != id)
                throw new InvalidDataException("Display names must retain their original rules/art identities: " + id);
        }
        var scene = GD.Load<PackedScene>("res://Scenes/UI/CardView.tscn");
        foreach (var profile in catalog.All)
        {
            var view = scene.Instantiate<CardView>();
            try
            {
                view.Bind(profile);
                if (view.GetNode<Label>("Margin/Column/StatsRarity/Rarity").GetThemeColor("font_color") != CardView.RarityColor(profile.Rarity))
                    throw new InvalidDataException("Rarity color was not applied to the visible label: " + profile.CardId);
                if (view.GetNode<Label>("Margin/Column/StatsRarity/Attack").Text != $"攻+{profile.Attack}" ||
                    view.GetNode<Label>("Margin/Column/StatsRarity/Defense").Text != $"防+{profile.Defense}" ||
                    view.GetNode<Label>("Margin/Column/StatsRarity/Rarity").Text != $"<{CardPresentationCatalog.RarityLabel(profile.Rarity)}>" ||
                    view.GetNode<Label>("Margin/Column/Details/Text/Enchantment").Visible ||
                    !string.IsNullOrEmpty(view.GetNode<Label>("Margin/Column/Details/Text/Enchantment").Text) ||
                    view.GetNode<Label>("Margin/Column/Title").HorizontalAlignment != HorizontalAlignment.Center)
                    throw new InvalidDataException("Card stats or removed enchantment hints are not rendered in the current format: " + profile.CardId);
                if (view.GetNode<Label>("Margin/Column/Title").Text != profile.DisplayName ||
                    view.GetMeta("card_id").AsString() != profile.CardId ||
                    view.GetMeta("profile_id").AsString() != profile.ProfileId ||
                    view.GetNode<Label>("Margin/Column/Details/Text/Rules").Text != CardView.FormatRulesText(profile.DisplayRulesText) ||
                    view.GetNode<Label>("Margin/Column/Details/Text/Rules").Text.Contains("毒附魔层数 +1", StringComparison.Ordinal) ||
                    !view.GetNode<Label>("Margin/Column/Metadata").Text.Contains(CardPresentationCatalog.ElementLabel(profile.Element), StringComparison.Ordinal) ||
                    !view.GetNode<Label>("Margin/Column/Metadata").Text.Contains(CardPresentationCatalog.RarityLabel(profile.Rarity), StringComparison.Ordinal) ||
                    !view.GetNode<Label>("Margin/Column/Header/Cost").Text.Contains($"{profile.CombatCost} 费用", StringComparison.Ordinal))
                    throw new InvalidDataException("Card view is missing required visible fields: " + profile.CardId);
                if (profile.Element == "generic" && !view.GetNode<Label>("Margin/Column/Metadata").Text.Contains("通用", StringComparison.Ordinal))
                    throw new InvalidDataException("Generic cards must explicitly display 通用.");
                foreach (var control in view.FindChildren("*", "Control", true, false).OfType<Control>())
                {
                    var visibleText = control switch
                    {
                        Label label => label.Text,
                        RichTextLabel rich => rich.Text,
                        Button button => button.Text,
                        _ => string.Empty
                    };
                    if (flavorTexts.Any(flavor => visibleText.Contains(flavor, StringComparison.Ordinal) ||
                        control.TooltipText.Contains(flavor, StringComparison.Ordinal)))
                        throw new InvalidDataException("Flavor text leaked into a card face or tooltip: " + profile.CardId);
                }
            }
            finally { view.Free(); }
        }
        var priceView = scene.Instantiate<CardView>();
        try
        {
            var catalogue = catalog.Get("禁咒目录");
            priceView.Bind(catalogue, 4, false);
            if (!priceView.GetNode<Label>("Margin/Column/Header/Cost").Text.Contains("1 费用", StringComparison.Ordinal) ||
                !priceView.GetNode<Label>("Margin/Column/Price").Text.Contains("4 研习点", StringComparison.Ordinal))
                throw new InvalidDataException("Combat energy cost and drafting study price must be distinguished.");
            priceView.Bind(catalog.Get("攻击强化"), 1, true);
            if (!priceView.GetNode<Label>("Margin/Column/Price").Text.Contains("本轮免费", StringComparison.Ordinal))
                throw new InvalidDataException("The current free-purchase entitlement must be shown on the card view.");
        }
        finally { priceView.Free(); }
        foreach (var sample in new[] { "回复 20 生命；立即/整场", "目标攻击 -2；整场", "获得 1 余烬；立即/下一发", "下次抽牌阶段多抽 1；下抽/下一发" })
            if (CardView.FormatRulesText(sample).Contains("立即", StringComparison.Ordinal) ||
                CardView.FormatRulesText(sample).Contains("整场", StringComparison.Ordinal) ||
                CardView.FormatRulesText(sample).EndsWith("；下一发", StringComparison.Ordinal) ||
                CardView.FormatRulesText(sample).EndsWith("；下抽", StringComparison.Ordinal))
                throw new InvalidDataException("Timing annotations must be hidden from card rules text: " + sample);
        var viewer = new PlayerId("human");
        var pairedNames = CombatLogText.Exchanges(new[]
        {
            new CombatEvent(1, 0, "CardPlayed", viewer, "火星"),
            new CombatEvent(1, 0, "CardPlayed", new PlayerId("opponent"), "火苗"),
            new CombatEvent(1, 0, "CardPlayed", viewer, "高温炉心")
        }, viewer, catalog);
        foreach (var expected in new[] { "【指尖火苗】", "【掌中火团】", "【炽红炉膛】" })
            if (!pairedNames.Contains(expected, StringComparison.Ordinal))
                throw new InvalidDataException("Played-card logs did not resolve names from the original card IDs: " + expected);
        GD.Print($"CARD_PRESENTATION_OK profiles={catalog.All.Count} views={catalog.All.Count}");
        GD.Print($"CARD_NAME_DISPLAY_OK renamed={catalog.All.Count(p => p.DisplayName != p.Name)} flavor-ui=hidden archived={creativeCards.Length}");
    }
}



