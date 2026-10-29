using Magicians.Core.Combat;
using Magicians.Core.Match;

namespace Magicians.Application;

// Only committed played-card events are retained. Opponent hands and pending
// actions never enter the review data, even after the tournament has ended.
public sealed class RecordedBattle(int round, Pairing pairing)
{
    public int Round { get; } = round;
    public Pairing Pairing { get; } = pairing;
    public List<CombatEvent> Events { get; } = new();
    private readonly List<CombatEvent> _plays = new();
    public IReadOnlyList<CombatEvent> Plays => _plays;
    public BattleResult? Result { get; internal set; }
    internal void Append(IEnumerable<CombatEvent> events) { var batch = events.ToArray(); Events.AddRange(batch); _plays.AddRange(batch.Where(e => e.Kind == "CardPlayed")); }
}
