using Godot;
using Magicians.Application;

namespace Magicians.Presentation;

public partial class BootController : Node
{
    private Control? _menu;
    private Control? _match;
    public override void _ExitTree() => GameSession.Current?.Dispose();
    public override void _Ready()
    {
        try
        {
            DisplayPreferences.Load().Apply();
            ShowMainMenu();
        }
        catch (Exception exception)
        {
            GD.PrintErr($"BOOT_FAILED {exception}");
            GetTree().Quit(1);
        }
    }

    private void ShowMainMenu()
    {
        _menu?.QueueFree();
        var scene = GD.Load<PackedScene>("res://Scenes/MainMenu/MainMenu.tscn");
        _menu = scene.Instantiate<Control>();
        AddChild(_menu);
        if (_menu is MainMenuController menu) menu.StartRequested += StartGame;
    }

    public void StartGame()
    {
        try
        {
            GameSession.Current?.Dispose();
            GameSession.Current = null;
            _match?.QueueFree();
            _menu?.QueueFree();
            _menu = null;
            var root = ProjectSettings.GlobalizePath("res://");
            GameSession.Current = GameSession.CreateSlice1(root);
            GameSession.Current.BeginDraft();
            _match = GD.Load<PackedScene>("res://Scenes/Match/Match.tscn").Instantiate<Control>();
            AddChild(_match);
        }
        catch (Exception exception)
        {
            GD.PrintErr($"START_GAME_FAILED {exception}");
            ShowMainMenu();
        }
    }

    public void ExitGame() => GetTree().Quit();
}
