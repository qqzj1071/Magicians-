using Godot;
using Magicians.Core.Cards;
using System.Text.Json;

namespace Magicians.Presentation;

// Canonical card names are shared by the client and rules authority.
public static class V12CardPresentation
{
    private static Dictionary<string, CardArtSlots>? _art;
    private static Dictionary<string, string>? _flavor;

    public static CardPresentationProfile Profile(JsonElement card)
    {
        if (_art is null)
        {
            _art = new(StringComparer.Ordinal);
            var path = Path.Combine(Magicians.Application.ClientPaths.DataRoot, "Data", "Presentation", "card-art.json");
            _art = JsonSerializer.Deserialize<Dictionary<string, CardArtSlots>>(File.ReadAllText(path)) ?? new(StringComparer.Ordinal);
        }
        var id = card.GetProperty("name").GetString()!;
        var rarity = card.GetProperty("rarity").GetString()!;
        var text = card.GetProperty("text").GetString()!;
        var layers = card.GetProperty("layers").GetInt32();
        if (_flavor is null)
        {
            var path = Path.Combine(Magicians.Application.ClientPaths.DataRoot, "Data", "Presentation", "card-flavor.json");
            using var document = JsonDocument.Parse(File.ReadAllText(path));
            _flavor = document.RootElement.GetProperty("cards").EnumerateObject()
                .ToDictionary(p => p.Name, p => p.Value.GetString()!, StringComparer.Ordinal);
        }
        return new(1, id, "v12:" + id, id, card.GetProperty("element").GetString()!, rarity,
            card.GetProperty("cost").GetInt32(), rarity switch { "common" => 1, "rare" => 2, "epic" => 3, "legendary" => 4, _ => 0 },
            card.GetProperty("attack").GetInt32(), card.GetProperty("defense").GetInt32(), layers,
            text, text, Array.Empty<string>(), _art.GetValueOrDefault(id) ?? new CardArtSlots(), _flavor.GetValueOrDefault(id, ""));
    }

    public static Control Face(JsonElement data, float width, float height, bool compact = false, bool combat = false)
    {
        var profile = Profile(data);
        var wrap = new Control { CustomMinimumSize = new Vector2(width, height), TooltipText = profile.Name + "\n" + profile.DisplayRulesText + (profile.FlavorText.Length > 0 ? "\n\n" + profile.FlavorText : "") };
        var face = GD.Load<PackedScene>("res://Scenes/UI/CardView.tscn").Instantiate<CardView>();
        wrap.AddChild(face);
        var scale = 1f;
        face.CustomMinimumSize = new Vector2(width / scale, height / scale);
        face.Size = face.CustomMinimumSize; face.Scale = new Vector2(scale, scale);
        face.Theme = new Theme { DefaultFontSize = 20 };
        // Battle hands and selection candidates carry per-instance authority state.
        // Catalogs and pile viewers do not imply a first play.
        var applied = !data.TryGetProperty("enchantment_applied", out var state) || state.GetBoolean();
        face.Bind(profile, combat: true, enchantmentApplied: !combat || applied);
        if (compact)
        {
            face.CustomMinimumSize = new Vector2(0, 0);
            foreach (var path in new[] { "Header/Element", "Header/Cost", "StatsRarity/Attack", "StatsRarity/Defense", "StatsRarity/Rarity" })
                face.GetNode<Label>("Margin/Column/" + path).AddThemeFontSizeOverride("font_size", 16);
            face.GetNode<Label>("Margin/Column/Title").AddThemeFontSizeOverride("font_size", 22);
            face.GetNode<Label>("Margin/Column/Details/Text/Rules").AddThemeFontSizeOverride("font_size", 18);
            face.GetNode<ColorRect>("Margin/Column/Art").CustomMinimumSize = new Vector2(0, 36);
        }
        if (!combat) face.GetNode<Label>("Margin/Column/Title").AddThemeColorOverride("font_color", Colors.White);
        face.GetNode<Label>("Margin/Column/Details/Text/Rules").Text = profile.DisplayRulesText;
        var details = face.GetNode<ScrollContainer>("Margin/Column/Details");
        details.VerticalScrollMode = ScrollContainer.ScrollMode.Auto;
        return wrap;
    }

    public static void Open(Control owner, string title, IEnumerable<JsonElement> cards)
    {
        var window = new Window { Title = title, Transient = true, Exclusive = true, Unresizable = true };
        owner.AddChild(window);
        var viewport = owner.GetWindow().Size;
        var width = (int)Math.Min(1800, viewport.X - 60); var height = (int)Math.Min(1000, viewport.Y - 60);
        var column = new VBoxContainer(); window.AddChild(column); column.SetAnchorsAndOffsetsPreset(Control.LayoutPreset.FullRect);
        column.OffsetLeft = 16; column.OffsetRight = -16; column.OffsetTop = 16; column.OffsetBottom = -16;
        var items = cards.ToArray();
        column.AddChild(new Label { Text = $"{title} · 共 {items.Length} 张", Theme = new Theme { DefaultFontSize = 26 } });
        var scroll = new ScrollContainer { SizeFlagsVertical = Control.SizeFlags.ExpandFill, HorizontalScrollMode = ScrollContainer.ScrollMode.Disabled };
        column.AddChild(scroll);
        var cols = Math.Clamp((width - 40) / 340, 1, 5);
        var grid = new GridContainer { Columns = cols }; grid.AddThemeConstantOverride("h_separation", 16); grid.AddThemeConstantOverride("v_separation", 16); scroll.AddChild(grid);
        foreach (var card in items) grid.AddChild(Face(card, (width - 48 - (cols-1)*16) / cols, 650));
        if (items.Length == 0) column.AddChild(new Label { Text = "这里暂时没有卡牌。" });
        var close = new Button { Text = "关闭", CustomMinimumSize = new Vector2(0, 44) }; close.Pressed += window.QueueFree; column.AddChild(close);
        window.CloseRequested += window.QueueFree;
        window.PopupCentered(new Vector2I(width, height));
    }
}
