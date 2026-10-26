using Godot;

namespace Magicians.Application;

// Local presentation preferences, never part of a match snapshot or its deterministic hash.
public sealed record DisplayPreferences(int Width = 1920, int Height = 1080, bool Fullscreen = false)
{
    public const string SettingsPath = "user://display.cfg";
    public DisplayPreferences Validated() => Width is >= 960 and <= 7680 && Height is >= 540 and <= 4320
        ? this : new DisplayPreferences(Fullscreen: Fullscreen);
    public static DisplayPreferences Load(string path = SettingsPath)
    {
        var config = new ConfigFile();
        if (config.Load(path) != Error.Ok) return new();
        try { return new DisplayPreferences((int)config.GetValue("display", "width", 1920),
            (int)config.GetValue("display", "height", 1080), (bool)config.GetValue("display", "fullscreen", false)).Validated(); }
        catch (Exception) { return new(); }
    }
    public Error Save(string path = SettingsPath)
    {
        var value = Validated(); var config = new ConfigFile();
        config.SetValue("display", "width", value.Width); config.SetValue("display", "height", value.Height);
        config.SetValue("display", "fullscreen", value.Fullscreen); return config.Save(path);
    }
    public void Apply()
    {
        if (DisplayServer.GetName() == "headless") return;
        var value = Validated();
        DisplayServer.WindowSetMode(DisplayServer.WindowMode.Windowed);
        DisplayServer.WindowSetFlag(DisplayServer.WindowFlags.ResizeDisabled, false);
        DisplayServer.WindowSetMinSize(new Vector2I(960, 540));
        DisplayServer.WindowSetSize(new Vector2I(value.Width, value.Height));
        var screen = DisplayServer.WindowGetCurrentScreen();
        DisplayServer.WindowSetPosition(DisplayServer.ScreenGetPosition(screen) +
            (DisplayServer.ScreenGetSize(screen) - new Vector2I(value.Width, value.Height)) / 2);
        if (value.Fullscreen) DisplayServer.WindowSetMode(DisplayServer.WindowMode.Fullscreen);
    }
}
