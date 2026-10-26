using System.Text.Json;
using Magicians.Core.Common;

namespace Magicians.Core.Draft;

// Read the frozen probabilities rather than maintaining a second probability table in code.
public sealed class FrozenDraftRules
{
    private readonly JsonElement _data;
    private FrozenDraftRules(JsonElement data) => _data = data;
    public static FrozenDraftRules Load(string path)
    {
        using var json = JsonDocument.Parse(File.ReadAllText(path));
        return new(json.RootElement.Clone());
    }
    public bool IsPity(int round) => _data.GetProperty("first_face_legendary_guarantees").TryGetProperty(round.ToString(), out _);
    public double[] Weights(int round, int face) => _data.GetProperty("rarities")
        .GetProperty(round >= 8 ? "8_plus" : round.ToString())[face].EnumerateArray().Select(v => v.GetDouble()).ToArray();
    public int[] Template(int round, int face, int count, IDeterministicRandom random)
    {
        var weights = Weights(round, face);
        return Enumerable.Range(0, count).Select(i => face == 0 && IsPity(round) && i < 3 ? 3 : Pick(weights, random)).ToArray();
    }
    public static double Unit(IDeterministicRandom random) => (random.NextInt(0, 1_000_000_000) + 0.5) / 1_000_000_000;
    public static int Pick(IReadOnlyList<double> weights, IDeterministicRandom random)
    {
        var ticket = Unit(random) * weights.Sum();
        for (var i = 0; i < weights.Count; i++) { ticket -= weights[i]; if (ticket < 0) return i; }
        return weights.Count - 1;
    }
    public static int Round(double value, IDeterministicRandom random) => (int)Math.Floor(value) + (Unit(random) < value - Math.Floor(value) ? 1 : 0);
    public int EnchantmentTarget(string? specialization, int activeCount, IDeterministicRandom random)
    {
        if (specialization is not null) return Round(_data.GetProperty("post_specialization_enchantment_share").GetDouble() * activeCount, random);
        var distribution = _data.GetProperty("pre_specialization_enchantment_count").EnumerateObject().ToArray();
        var target = int.Parse(distribution[Pick(distribution.Select(p => p.Value.GetDouble()).ToArray(), random)].Name);
        return Round(target * activeCount / 8.0, random);
    }
    public double BoughtElementAdmission => _data.GetProperty("refresh_bought_element_admission").GetDouble();
    public string LegendaryType(int round, IDeterministicRandom random, bool allowRoute = true)
    {
        var weights = _data.GetProperty("legendary_types").GetProperty(round <= 8 ? "6_to_8" : "9_plus")
            .EnumerateArray().Select(v => v.GetDouble()).ToArray();
        if (!allowRoute) weights[0] = 0;
        return _data.GetProperty("legendary_type_order")[Pick(weights, random)].GetString()!;
    }
    public bool IsEngine(string name) => _data.GetProperty("generic_engine_legendaries").EnumerateArray().Any(v => v.GetString() == name);
}
