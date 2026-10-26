using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Magicians.Core.Match;

namespace Magicians.Core.Common;

public static class StateHasher
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = false
    };

    public static string Hash(MatchState state)
    {
        var projection = new
        {
            state.Id,
            state.Round,
            state.Phase,
            state.Seed,
            state.RandomState,
            state.InitialStudyPoints,
            state.OffersPerPlayer,
            state.AllowRefresh,
            state.AllowRemove,
            state.AllowSpecialization,
            state.AllowRouteSelection,
            state.EventSequence,
            Players = state.Players
                .OrderBy(pair => pair.Key.Value, StringComparer.Ordinal)
                .Select(pair => pair.Value)
                .ToArray(),
            Inventory = state.SharedCardInventory
                .OrderBy(pair => pair.Key, StringComparer.Ordinal)
                .ToArray(),
            Pairings = state.Pairings.ToArray()
            ,BattleResults = state.BattleResults.ToArray(),
            PairingHistory = state.PairingHistory.ToArray(),
            RoundHistory = state.RoundHistory.ToArray(),
            NextRoundStudyPoints = state.NextRoundStudyPoints
                .OrderBy(pair => pair.Key.Value, StringComparer.Ordinal).ToArray(),
            GhostSnapshots = state.GhostSnapshots
                .OrderBy(pair => pair.Key.Value, StringComparer.Ordinal).Select(pair => pair.Value).ToArray()
            ,PendingPoolReturns = state.PendingPoolReturns.OrderBy(pair => pair.Key, StringComparer.Ordinal).ToArray()
            ,UnseenLegendaryCopies = state.UnseenLegendaryCopies.OrderBy(pair => pair.Key, StringComparer.Ordinal).ToArray()
        };
        var json = JsonSerializer.Serialize(projection, JsonOptions);
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(json))).ToLowerInvariant();
    }
}
