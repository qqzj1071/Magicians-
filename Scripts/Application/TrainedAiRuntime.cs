using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Magicians.Core.AI;
using Magicians.Core.Cards;
using Magicians.Core.Combat;
using Magicians.Core.Common;
using Magicians.Core.Match;

namespace Magicians.Application;

public sealed record AiDecisionTrace(string Stage, int Round, string Player, string ObservationHash,
    string ModelHash, string Decision, string Reason);

/// <summary>One persistent, hidden, inference-only worker per participant. Requests
/// contain only the explicit observation DTOs. No simple-policy fallback.</summary>
public sealed class TrainedAiRuntime : IDisposable
{
    private readonly string _root;
    private readonly string _python;
    private readonly object _gate = new();
    private readonly Dictionary<string, Process> _processes = new(StringComparer.Ordinal);
    private readonly Dictionary<string, object> _participantGates = new(StringComparer.Ordinal);
    private volatile bool _disposed;
    private readonly List<AiDecisionTrace> _traces = new();
    public IReadOnlyList<AiDecisionTrace> Traces { get { lock (_gate) return _traces.ToArray(); } }
    public int WorkerCount { get { lock (_gate) return _processes.Count; } }
    public string ModelHash { get; }
    public IReadOnlyDictionary<string, string> SourceHashes { get; }

    public TrainedAiRuntime(string root)
    {
        _root = Path.GetFullPath(root);
        using var pointer = JsonDocument.Parse(File.ReadAllText(Path.Combine(root, "docs", "ai", "current-tournament.json")));
        var model = pointer.RootElement.GetProperty("model").GetString()!;
        ModelHash = HashFile(Path.Combine(root, model));
        if (ModelHash != pointer.RootElement.GetProperty("model_sha256").GetString())
            throw new InvalidDataException("Recommended AI checkpoint hash mismatch.");
        SourceHashes = new[] { model, "releases/v1.0/cards.json", "tools/round_robin/engine.py", "tools/round_robin/planner.py", "tools/round_robin/policies.json",
            "tools/round_robin/strategic_tournament_ai.py", "tools/round_robin/shared_draft_combat.py", "tools/client_ai/inference_worker.py",
            "Scripts/Core/AI/AiObservations.cs", "Scripts/Application/TrainedAiRuntime.cs", "Scripts/Core/Combat/Slice1CombatEngine.cs", "Scripts/Core/Match/MatchCoordinator.cs",
            "Scripts/Core/Draft/FrozenDraftRules.cs", "Scripts/Core/Draft/DraftOfferAllocator.cs", "releases/deckbuilding-v1.0/probabilities.json",
            "releases/deckbuilding-v1.0/pool-counts.json", "releases/deckbuilding-v1.0/economy.json" }
            .ToDictionary(path => path, path => HashFile(Path.Combine(root, path)), StringComparer.Ordinal);
        using var settings = JsonDocument.Parse(File.ReadAllText(Path.Combine(root, "tools", "client_ai", "runtime.json")));
        _python = Environment.GetEnvironmentVariable("MAGICIANS_PYTHON") ?? settings.RootElement.GetProperty("pythonExecutable").GetString()!;
        if (!Path.IsPathRooted(_python)) _python = Path.GetFullPath(Path.Combine(root, _python));
        if (!File.Exists(_python)) throw new FileNotFoundException("AI Python runtime unavailable; set MAGICIANS_PYTHON or tools/client_ai/runtime.json.", _python);
    }

    private static string HashFile(string path) => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();

    private Process EnsureStarted(string player)
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
        if (_processes.TryGetValue(player, out var existing) && !existing.HasExited) return existing;
        var start = new ProcessStartInfo(_python)
        {
            WorkingDirectory = _root, UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardInput = true, RedirectStandardOutput = true, RedirectStandardError = true,
            StandardInputEncoding = new UTF8Encoding(false), StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8
        };
        start.ArgumentList.Add("-u");
        start.ArgumentList.Add(Path.Combine(_root, "tools", "client_ai", "inference_worker.py"));
        start.Environment["PYTHONIOENCODING"] = "utf-8";
        start.Environment["PYTHONHASHSEED"] = "0";
        start.Environment["PYTHONDONTWRITEBYTECODE"] = "1";
        start.Environment.Remove("MAGICIANS_CARD_LIBRARY");
        var worker = Process.Start(start) ?? throw new InvalidOperationException("Unable to start AI inference worker.");
        _processes[player] = worker;
        worker.ErrorDataReceived += (_, _) => { }; // Drain stderr so a traceback cannot block stdout.
        worker.BeginErrorReadLine();
        return worker;
    }

    private JsonElement Request(string kind, object view, int round, string player)
    {
        object participantGate;
        lock (_gate)
        {
            ObjectDisposedException.ThrowIf(_disposed, this);
            if (!_participantGates.TryGetValue(player, out participantGate!))
                _participantGates[player] = participantGate = new object();
        }
        // Each participant owns a separate Python process. Only requests to that
        // process serialize; another battle must never hold up this actor's reply.
        lock (participantGate)
        {
            Process worker;
            lock (_gate) worker = EnsureStarted(player);
            worker.StandardInput.WriteLine(JsonSerializer.Serialize(new { kind, actor = player, view }, AiObservations.Json));
            worker.StandardInput.Flush();
            var read = worker.StandardOutput.ReadLineAsync();
            if (!read.Wait(TimeSpan.FromSeconds(30)))
            {
                worker.Kill(true);
                throw new TimeoutException("AI inference exceeded the 30-second worker limit.");
            }
            var line = read.Result ?? throw new InvalidOperationException("AI worker exited without a decision.");
            using var response = JsonDocument.Parse(line);
            if (!response.RootElement.GetProperty("ok").GetBoolean())
                throw new InvalidOperationException("AI inference failed: " + response.RootElement.GetProperty("error").GetString());
            if (response.RootElement.GetProperty("modelHash").GetString() != ModelHash)
                throw new InvalidDataException("AI worker loaded an unexpected model.");
            if (response.RootElement.GetProperty("cardHash").GetString() != SourceHashes["releases/v1.0/cards.json"])
                throw new InvalidDataException("AI worker loaded a different card library from the client.");
            var result = response.RootElement.GetProperty("result").Clone();
            lock (_gate)
                _traces.Add(new(kind, round, player, AiObservations.Hash(view), ModelHash, result.GetRawText(),
                    result.TryGetProperty("reason", out var reason) ? reason.ToString() : ""));
            return result;
        }
    }

    public AiLegalDraftAction ChooseDraft(AiDraftView view)
    {
        var result = Request("draft", view, view.Round, view.Player);
        var action = result.GetProperty("action").Deserialize<AiLegalDraftAction>(AiObservations.Json)
            ?? throw new InvalidDataException("Empty trained draft decision.");
        if (!view.LegalActions.Contains(action)) throw new InvalidDataException("AI returned an action outside its legal draft action set.");
        return action;
    }

    public CombatAction ChooseCombat(AiCombatView view)
    {
        var result = Request("combat", view, view.Round, view.Player);
        if (result.GetProperty("kind").GetString() == "end") return new(CombatActionKind.EndWindow);
        var id = result.GetProperty("card").GetString()!;
        if (!view.Hand.Any(c => c.Id == id)) throw new InvalidDataException("AI chose a card outside its visible hand.");
        return new(CombatActionKind.PlayCard, new CardInstanceId(id));
    }

    public CombatAction ChooseSearch(CombatAction selected, SearchSelectionSession session, AiCombatView combatContext)
    {
        if (session.Candidates.Count == 0) return selected;
        var view = new { SourceCard = session.CardId, session.MaximumSelections, CombatContext = combatContext,
            Candidates = session.Candidates.Select(c => new AiOwnedCard(c.InstanceId.Value, c.CardId)).ToArray() };
        var result = Request("search", view, combatContext.Round, session.Player.Value);
        var ids = result.GetProperty("targets").EnumerateArray().Select(v => new CardInstanceId(v.GetString()!)).ToArray();
        if (ids.Length > session.MaximumSelections || ids.Distinct().Count() != ids.Length ||
            ids.Any(id => !session.Candidates.Any(c => c.InstanceId == id))) throw new InvalidDataException("AI chose an unrevealed search target.");
        return session.MaximumSelections > 1 ? selected with { SearchTargets = ids, SearchTarget = null }
            : selected with { SearchTarget = ids.FirstOrDefault(), SearchTargets = null };
    }

    public static IGameCommand DraftCommand(MatchState state, PlayerId player, AiLegalDraftAction action)
    {
        var sequence = new CommandSequence(state.EventSequence + 1);
        return action.Kind switch
        {
            "buy" => new BuyCardCommand(state.Id, player, action.Slot!, sequence)
                { ReplaceCard = action.Replace is null ? null : new CardInstanceId(action.Replace) },
            "refresh" => new RefreshOffersCommand(state.Id, player, sequence),
            "remove" => new RemoveCardCommand(state.Id, player, new(action.Card!), sequence),
            "finish" => new FinishDraftCommand(state.Id, player, sequence),
            _ => throw new InvalidDataException("Unknown trained draft action: " + action.Kind)
        };
    }

    public void Dispose()
    {
        (Process Worker, object Gate)[] workers;
        lock (_gate)
        {
            if (_disposed) return;
            _disposed = true;
            workers = _processes.Select(p => (p.Value, _participantGates[p.Key])).ToArray();
            _processes.Clear();
        }
        foreach (var (worker, participantGate) in workers)
            lock (participantGate)
            {
                if (!worker.HasExited) { worker.StandardInput.Close(); if (!worker.WaitForExit(1500)) worker.Kill(true); }
                worker.Dispose();
            }
    }
}
