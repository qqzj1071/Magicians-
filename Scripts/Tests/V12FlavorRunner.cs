using Godot;
using Magicians.Presentation;
using System.Text.Json;

namespace Magicians.Tests;

public partial class V12FlavorRunner : Node
{
    public override async void _Ready()
    {
        try
        {
            GetWindow().Size = new Vector2I(1920, 1080);
            using var document = JsonDocument.Parse(File.ReadAllText(ProjectSettings.GlobalizePath("res://releases/v1.2/cards.json")));
            foreach (var element in new[] { "fire", "water", "earth", "wind", "poison" })
            {
                var panel = new HBoxContainer { Position = new Vector2(20, 24), Size = new Vector2(1880, 1000) };
                panel.AddThemeConstantOverride("separation", 12); AddChild(panel);
                var cards = document.RootElement.GetProperty("cards").EnumerateObject().Select(p => p.Value)
                    .Where(c => c.GetProperty("element").GetString() == element && new[] { "legendary", "specialization" }.Contains(c.GetProperty("rarity").GetString())).ToArray();
                if (cards.Length != 5) throw new Exception("Flavor gallery requires five cards per element");
                foreach (var card in cards) panel.AddChild(V12CardPresentation.Face(card, 366, 1000));
                for (var frame = 0; frame < 5; frame++) await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
                await ToSignal(RenderingServer.Singleton, RenderingServer.SignalName.FramePostDraw);
                var target = ProjectSettings.GlobalizePath("res://../runtime/canonical-" + element + ".png");
                if (GetViewport().GetTexture().GetImage().SavePng(target) != Error.Ok) throw new IOException(target);
                panel.Free();
            }
            GD.Print("V12_FLAVOR_GALLERY_OK cards=25 elements=5"); GetTree().Quit();
        }
        catch (Exception e) { GD.PushError(e.ToString()); GetTree().Quit(1); }
    }
}
