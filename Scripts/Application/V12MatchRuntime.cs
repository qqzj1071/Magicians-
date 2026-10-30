using System.Diagnostics;
using System.Text;
using System.Text.Json;

namespace Magicians.Application;

// A dedicated process retains the canonical tournament and both planning stacks.
// All UI commands are serialized and checked against an authority revision.
public sealed class V12MatchRuntime : IDisposable
{
    private readonly Process _process;
    private readonly SemaphoreSlim _requests = new(1, 1);
    private readonly Task<string> _errors;
    private bool _disposed;
    public long Revision { get; private set; }

    public V12MatchRuntime(string root)
    {
        var start = new ProcessStartInfo
        {
            FileName = V12CombatRuntime.PythonExecutable(), WorkingDirectory = root,
            UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardInput = true, RedirectStandardOutput = true, RedirectStandardError = true,
            StandardInputEncoding = new UTF8Encoding(false), StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8
        };
        start.ArgumentList.Add("-u"); start.ArgumentList.Add("-m"); start.ArgumentList.Add("tools.client_v12.match");
        _process = Process.Start(start) ?? throw new IOException("无法启动 v1.2 单人赛事。");
        _errors = _process.StandardError.ReadToEndAsync();
    }

    public Task<JsonElement> Start(int seed, string[] styles) => Request(new { op = "start", seed, ai_styles = styles });

    public Task<JsonElement> Review(int round) => Request(new { op = "review", round });

    public Task<JsonElement> Submit(string kind, int? slot = null, int? index = null, string? uid = null, string[]? uids = null) =>
        Request(new { kind, revision = Revision, slot, index, uid, uids });

    private async Task<JsonElement> Request(object request)
    {
        await _requests.WaitAsync();
        try
        {
            ObjectDisposedException.ThrowIf(_disposed, this);
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(120));
            await _process.StandardInput.WriteLineAsync(JsonSerializer.Serialize(request).AsMemory(), timeout.Token);
            await _process.StandardInput.FlushAsync(timeout.Token);
            var line = await _process.StandardOutput.ReadLineAsync(timeout.Token);
            if (line is null) throw new IOException("v1.2 赛事进程已退出：" + await _errors);
            using var json = JsonDocument.Parse(line);
            var result = json.RootElement.Clone();
            if (result.GetProperty("status").GetString() == "error")
                throw new InvalidDataException(result.GetProperty("error").GetString());
            Revision = result.GetProperty("revision").GetInt64();
            return result;
        }
        catch (OperationCanceledException)
        {
            Dispose();
            throw new TimeoutException("v1.2 赛事响应超时，请重新开始赛事。");
        }
        finally { _requests.Release(); }
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        if (!_process.HasExited) _process.Kill(true);
        _process.Dispose();
    }
}
