using Godot;
using Magicians.Core.Cards;
using Magicians.Presentation;

namespace Magicians.Tests;

public static class CardPresentationRegression
{
    public static void Run(CardDatabase database, string root)
    {
        var catalog = CardPresentationCatalog.Load(database, Path.Combine(root, "Data", "Presentation", "Cards"));
        var scene = GD.Load<PackedScene>("res://Scenes/UI/CardView.tscn");
        foreach (var profile in catalog.All)
        {
            var view = scene.Instantiate<CardView>();
            try
            {
                view.Bind(profile);
                if (view.GetNode<Label>("Margin/Column/Details/Text/StatsRarity/Rarity").GetThemeColor("font_color") != CardView.RarityColor(profile.Rarity))
                    throw new InvalidDataException("Rarity color was not applied to the visible label: " + profile.CardId);
                if (view.GetNode<Label>("Margin/Column/Title").Text != profile.Name ||
                    view.GetNode<Label>("Margin/Column/Details/Text/Rules").Text != CardView.FormatRulesText(profile.DisplayRulesText) ||
                    !view.GetNode<Label>("Margin/Column/Metadata").Text.Contains(CardPresentationCatalog.ElementLabel(profile.Element), StringComparison.Ordinal) ||
                    !view.GetNode<Label>("Margin/Column/Metadata").Text.Contains(CardPresentationCatalog.RarityLabel(profile.Rarity), StringComparison.Ordinal) ||
                    !view.GetNode<Label>("Margin/Column/Header/Cost").Text.Contains($"{profile.CombatCost} 费用", StringComparison.Ordinal))
                    throw new InvalidDataException("Card view is missing required visible fields: " + profile.CardId);
                if (profile.Element == "generic" && !view.GetNode<Label>("Margin/Column/Metadata").Text.Contains("通用", StringComparison.Ordinal))
                    throw new InvalidDataException("Generic cards must explicitly display 通用.");
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
        GD.Print($"CARD_PRESENTATION_OK profiles={catalog.All.Count} views={catalog.All.Count}");
    }
}


