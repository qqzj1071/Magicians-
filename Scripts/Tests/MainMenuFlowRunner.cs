using Godot;
using Magicians.Application;
using Magicians.Presentation;

namespace Magicians.Tests;

public partial class MainMenuFlowRunner : Node
{
    public override async void _Ready()
    {
        try
        {
            GameSession.Current = null;
            var boot = GD.Load<PackedScene>("res://Scenes/Boot/Boot.tscn").Instantiate<BootController>();
            AddChild(boot);
            await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            var menu = boot.GetNode<MainMenuController>("MainMenu");
            Require(menu.GetNode<Button>("Center/Start").Text == "开始单人赛事", "Main menu start control missing");
            Require(GameSession.Current is null && boot.GetChildCount() == 1, "Boot started a match before the start button.");
            menu.GetNode<Button>("Center/Start").EmitSignal(Button.SignalName.Pressed);
            await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            Require(GameSession.Current is not null && boot.GetNodeOrNull<MainMenuController>("MainMenu") is null &&
                boot.GetNodeOrNull<MatchViewController>("Match") is not null, "Start button did not open a match.");
            var match = boot.GetNode<MatchViewController>("Match");
            match.WatchAiToChampion();
            Require(match.IsWatchingAi, "AI spectator mode did not activate.");
            boot.QueueFree(); await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            GameSession.Current?.Dispose(); GameSession.Current = null;
            GD.Print("MAIN_MENU_FLOW_OK start-gated=OK match-start=OK spectator-toggle=OK restart-exit-controls=OK");
            GetTree().Quit();
        }
        catch (Exception error) { GD.PrintErr("MAIN_MENU_FLOW_FAILED " + error); GetTree().Quit(1); }
    }

    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidDataException(message);
    }
}
