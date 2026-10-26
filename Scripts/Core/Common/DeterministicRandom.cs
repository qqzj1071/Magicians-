namespace Magicians.Core.Common;

public interface IDeterministicRandom
{
    int NextInt(int minInclusive, int maxExclusive);
    void Shuffle<T>(IList<T> items);
    ulong State { get; }
}

public sealed class SeededRandom : IDeterministicRandom
{
    private ulong _state;

    public SeededRandom(int seed)
    {
        _state = unchecked((ulong)(uint)seed) + 0x9E3779B97F4A7C15UL;
        if (_state == 0)
            _state = 0xA4093822299F31D0UL;
    }

    private SeededRandom(ulong state) => _state = state == 0 ? 0xA4093822299F31D0UL : state;

    public static SeededRandom FromState(ulong state) => new(state);

    public ulong State => _state;

    public int NextInt(int minInclusive, int maxExclusive)
    {
        if (minInclusive >= maxExclusive)
            throw new ArgumentOutOfRangeException(nameof(maxExclusive));
        var range = (ulong)(maxExclusive - minInclusive);
        return minInclusive + (int)(NextUInt64() % range);
    }

    public void Shuffle<T>(IList<T> items)
    {
        for (var i = items.Count - 1; i > 0; i--)
        {
            var j = NextInt(0, i + 1);
            (items[i], items[j]) = (items[j], items[i]);
        }
    }

    private ulong NextUInt64()
    {
        var value = _state;
        value ^= value >> 12;
        value ^= value << 25;
        value ^= value >> 27;
        _state = value;
        return value * 2685821657736338717UL;
    }
}
