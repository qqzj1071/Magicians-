using Magicians.Core.Common;

namespace Magicians.Core.Cards;

public sealed record CardInstance(
    CardInstanceId InstanceId,
    string CardId,
    PlayerId Owner
);
