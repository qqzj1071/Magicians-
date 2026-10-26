using System.Text.Json;

namespace Magicians.Core.Match;

public sealed record Slice1Scenario(
    string Id,
    string Version,
    int Round,
    int InitialTournamentLife,
    int InitialStudyPoints,
    int OffersPerPlayer,
    bool AllowRefresh,
    bool AllowRemove,
    bool AllowSpecialization,
    bool AllowRouteSelection,
    string CardPoolFile,
    string SourceCardsFile,
    IReadOnlyList<IReadOnlyList<string>> FixedPairings
)
{
    public static Slice1Scenario Load(string path)
    {
        if (!File.Exists(path))
            throw new FileNotFoundException("Slice 1 scenario was not found.", path);

        var json = File.ReadAllText(path);
        return JsonSerializer.Deserialize<Slice1Scenario>(json, new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true
        }) ?? throw new InvalidDataException("Slice 1 scenario JSON was empty.");
    }
}
