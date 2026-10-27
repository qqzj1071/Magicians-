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
            if (!OS.HasFeature("editor"))
                ReleaseIntegrity.Verify(Path.GetDirectoryName(OS.GetExecutablePath())!);
            DisplayPreferences.Load().Apply();
            ShowMainMenu();
            if (OS.GetCmdlineUserArgs().Contains("--release-smoke"))
            {
                StartGame();
                AddChild(new Magicians.Tests.ReleaseSmokeRunner());
            }
        }
        catch (Exception exception)
        {
            GD.PrintErr($"BOOT_FAILED {exception}");
            if (!DisplayServer.GetName().Equals("headless", StringComparison.Ordinal))
                OS.Alert(exception.Message, "Magicians! 文件校验失败");
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
            var root = ClientPaths.DataRoot;
            GameSession.Current = GameSession.CreateSlice1(root);
            GameSession.Current.BeginDraft();
            _match = GD.Load<PackedScene>("res://Scenes/Match/Match.tscn").Instantiate<Control>();
            AddChild(_match);
        }
        catch (Exception exception)
        {
            GD.PrintErr($"START_GAME_FAILED {exception}");
            OS.Alert(exception.Message, "Magicians! 启动失败");
            ShowMainMenu();
        }
    }

    public void ExitGame() => GetTree().Quit();
}

