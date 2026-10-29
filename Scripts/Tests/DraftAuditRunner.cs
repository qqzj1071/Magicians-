using Godot;
using Magicians.Core.Cards;
using Magicians.Presentation;

namespace Magicians.Tests;

public partial class DraftAuditRunner : Node
{
    public override void _Ready()
    {
        try
        {
            var root = ProjectSettings.GlobalizePath("res://");
            var cards = CardDatabase.LoadFromJson(Path.Combine(root, "releases/v1.1/cards.json"));
            var pool = Slice1CardPool.LoadFull(Path.Combine(root, "releases/deckbuilding-v1.0/pool-counts.json"),
                Path.Combine(root, "releases/deckbuilding-v1.0/economy.json"), cards);
            DraftAllocationRegression.Run(cards, pool, root);
            if ((int)ProjectSettings.GetSetting("display/window/size/viewport_width") != 1920 ||
                (int)ProjectSettings.GetSetting("display/window/size/viewport_height") != 1080 ||
                (int)ProjectSettings.GetSetting("display/window/size/window_width_override") != 1920 ||
                (int)ProjectSettings.GetSetting("display/window/size/window_height_override") != 1080)
                throw new InvalidDataException("Default client resolution mismatch.");
            var dialog = new DisplaySettingsDialog(); AddChild(dialog); dialog.PopupCentered(new Vector2I(560, 180));
            var controls = dialog.GetChildren().OfType<VBoxContainer>().Single().GetChildren();
            if (controls.OfType<OptionButton>().Single().ItemCount < 5 || !controls.OfType<CheckBox>().Any() || dialog.GetOkButton().Text != "应用并保存")
                throw new InvalidDataException("Display settings controls missing.");
            dialog.Hide();
            GD.Print("DRAFT_ALLOCATION_AUDIT_OK rounds=20 seeds=12 cases=240; DISPLAY_SETTINGS_OK");
            GetTree().Quit();
        }
        catch (Exception e) { GD.PrintErr("DRAFT_AUDIT_FAILED " + e); GetTree().Quit(1); }
    }
}
