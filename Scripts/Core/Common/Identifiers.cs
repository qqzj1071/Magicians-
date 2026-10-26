namespace Magicians.Core.Common;

public readonly record struct MatchId(string Value)
{
    public override string ToString() => Value;
}

public readonly record struct PlayerId(string Value)
{
    public override string ToString() => Value;
}

public readonly record struct BattleId(string Value)
{
    public override string ToString() => Value;
}

public readonly record struct CardInstanceId(string Value)
{
    public override string ToString() => Value;
}
