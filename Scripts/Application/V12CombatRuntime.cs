using System.Diagnostics;
using System.Text;
using System.Text.Json;

namespace Magicians.Application;

// The frozen Python authority owns all v1.2 effects and exact arithmetic.
// Requests contain JSON choices, never executable scripts or pickle payloads.
public static class V12CombatRuntime
{
    public static async Task<JsonElement> Request(string root, object request)
    {
        var start = new ProcessStartInfo
        {
            FileName = PythonExecutable(),
            WorkingDirectory = root,
            UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardInput = true, RedirectStandardOutput = true, RedirectStandardError = true,
            StandardInputEncoding = new UTF8Encoding(false), StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8
        };
        start.ArgumentList.Add("-m"); start.ArgumentList.Add("tools.client_v12.bridge");
        using var process = Process.Start(start) ?? throw new IOException("Cannot start v1.2 authority.");
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(60));
        try
        {
            var output = process.StandardOutput.ReadToEndAsync(timeout.Token);
            var errors = process.StandardError.ReadToEndAsync(timeout.Token);
            await process.StandardInput.WriteAsync(JsonSerializer.Serialize(request));
            process.StandardInput.Close();
            await process.WaitForExitAsync(timeout.Token);
            var text = await output;
            if (process.ExitCode != 0) throw new IOException(await errors);
            using var json = JsonDocument.Parse(text);
            var result = json.RootElement.Clone();
            if (result.TryGetProperty("status", out var status) && status.GetString() == "error")
                throw new InvalidDataException(result.GetProperty("error").GetString());
            return result;
        }
        catch
        {
            if (!process.HasExited) process.Kill(true);
            throw;
        }
    }

    internal static string PythonExecutable()
    {
        var configured = Environment.GetEnvironmentVariable("MAGICIANS_PYTHON");
        if (!string.IsNullOrWhiteSpace(configured)) return configured;
        var bundled = Path.Combine(Path.GetDirectoryName(Godot.OS.GetExecutablePath())!, "runtime-data", "python", "python.exe");
        if (!Godot.OS.HasFeature("editor") && File.Exists(bundled)) return bundled;
        var local = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "AppData", "Local");
        var pythonRoot = Path.Combine(local, "Programs", "Python");
        if (Directory.Exists(pythonRoot))
            foreach (var folder in Directory.EnumerateDirectories(pythonRoot, "Python*").OrderByDescending(x => x))
            {
                var installed = Path.Combine(folder, "python.exe");
                if (File.Exists(installed)) return installed;
            }
        return "python";
    }
}
