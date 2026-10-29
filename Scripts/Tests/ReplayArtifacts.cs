using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Magicians.Application;
using Magicians.Core.Combat;
using Magicians.Core.Common;
using Magicians.Core.Match;

namespace Magicians.Tests;

public static class ReplayArtifacts
{
    private static string Digest(string value) => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value))).ToLowerInvariant();
    public static void Save(string root, int seed, int run, GameSession session,
        IReadOnlyList<(int Round, BattleId Battle, CombatEvent Event)> combatEvents)
    {
        var state = session.Coordinator.CurrentState;
        var events = state.EventLog.Select(e => new { e.Round, e.Sequence, Kind = e.GetType().Name, e.StateHash }).ToArray();
        var battleSummary = combatEvents.GroupBy(e => (e.Round, e.Battle.Value)).Select(group => new
        {
            Round = group.Key.Round, Battle = group.Key.Value, Events = group.Count(),
            Counts = group.GroupBy(e => e.Event.Kind).OrderBy(g => g.Key, StringComparer.Ordinal).ToDictionary(g => g.Key, g => g.Count()),
            Hash = Digest(JsonSerializer.Serialize(group.Select(e => e.Event)))
        }).ToArray();
        var eventHash = Digest(JsonSerializer.Serialize(new { events, battleSummary }));
        var artifact = new
        {
            SchemaVersion = 1, Seed = seed, Run = run, Policy = "recommended-trained-python-inference",
            session.Ai.ModelHash, session.Ai.SourceHashes, Rules = "cards-v1.1/client-current",
            FinalStateHash = StateHasher.Hash(state), EventSummaryHash = eventHash, Rounds = state.Round,
            Champions = TournamentStandings.Champions(state).Select(id => id.Value).ToArray(),
            Standings = TournamentStandings.Calculate(state), TournamentEvents = events, Battles = battleSummary,
            Decisions = session.Ai.Traces
        };
        var directory = Path.GetFullPath(Path.Combine(root, "..", "runtime", "regressions", "trained-ai", "seed-" + seed));
        Directory.CreateDirectory(directory);
        var options = new JsonSerializerOptions { WriteIndented = true, Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping };
        var path = Path.Combine(directory, $"run-{run}.json");
        File.WriteAllText(path, JsonSerializer.Serialize(artifact, options));
        var baselinePath = Path.Combine(root, "Data", "Regression", "trained-ai-v1.1-baselines.json");
        if (File.Exists(baselinePath))
        {
            using var baseline = JsonDocument.Parse(File.ReadAllText(baselinePath));
            if (baseline.RootElement.GetProperty("ModelHash").GetString() != session.Ai.ModelHash)
                throw new InvalidDataException("Trained AI model changed; review and explicitly update replay baselines.");
            var expected = baseline.RootElement.GetProperty("Seeds").GetProperty(seed.ToString(System.Globalization.CultureInfo.InvariantCulture));
            if (expected.GetProperty("FinalStateHash").GetString() != artifact.FinalStateHash ||
                expected.GetProperty("EventSummaryHash").GetString() != eventHash)
                throw new InvalidDataException("Pinned trained replay baseline changed: " + seed);
        }
        if (run > 1)
        {
            using var first = JsonDocument.Parse(File.ReadAllText(Path.Combine(directory, "run-1.json")));
            if (first.RootElement.GetProperty("FinalStateHash").GetString() != artifact.FinalStateHash ||
                first.RootElement.GetProperty("EventSummaryHash").GetString() != eventHash)
                throw new InvalidDataException("Multi-round replay diverged in state or event digest: " + seed);
        }
    }

    public static void SaveIndex(string root)
    {
        var directory = Path.GetFullPath(Path.Combine(root, "..", "runtime", "regressions", "trained-ai"));
        var runs = new List<object>();
        foreach (var file in Directory.EnumerateFiles(directory, "run-*.json", SearchOption.AllDirectories).OrderBy(p => p, StringComparer.Ordinal))
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(file));
            var r = doc.RootElement;
            runs.Add(new { Seed = r.GetProperty("Seed").GetInt32(), Run = r.GetProperty("Run").GetInt32(),
                Rounds = r.GetProperty("Rounds").GetInt32(), FinalStateHash = r.GetProperty("FinalStateHash").GetString(),
                EventSummaryHash = r.GetProperty("EventSummaryHash").GetString(), ModelHash = r.GetProperty("ModelHash").GetString(),
                Decisions = r.GetProperty("Decisions").GetArrayLength(), File = Path.GetRelativePath(directory, file) });
        }
        File.WriteAllText(Path.Combine(directory, "summary.json"), JsonSerializer.Serialize(new
        { SchemaVersion = 1, Status = "passed", RepeatedStateAndEventHashesVerified = true, Runs = runs }, new JsonSerializerOptions { WriteIndented = true }));
    }
}
