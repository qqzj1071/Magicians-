using System.Security.Cryptography;
using System.Text;
using Magicians.Core.Cards;
using Magicians.Core.Common;

namespace Magicians.Core.Combat;

/// <summary>Immutable per-round deck input. Battle instances never retain a mutable PlayerState reference.</summary>
public sealed record DeckSnapshot(
    PlayerId Player,
    int Round,
    IReadOnlyList<CardInstance> Cards,
    string Fingerprint)
{
    public static DeckSnapshot Create(PlayerId player, int round, IEnumerable<CardInstance> cards)
    {
        var frozen = cards.Select(card => card with { }).ToArray();
        var payload = string.Join("|", frozen.Select(card => $"{card.InstanceId.Value}:{card.CardId}:{card.Owner.Value}"));
        var fingerprint = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(payload))).ToLowerInvariant();
        return new DeckSnapshot(player, round, Array.AsReadOnly(frozen), fingerprint);
    }
}
