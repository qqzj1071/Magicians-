using Magicians.Core.Cards;
using Magicians.Core.Combat;
using Magicians.Core.Common;

namespace Magicians.Application;

public sealed record PublicCombatantView(PlayerId Player, int Life, int Shield, int Attack, int Defense, int Energy)
{
    public static PublicCombatantView From(CombatantState state) =>
        new(state.Player, state.Life, state.Shield, state.Attack, state.Defense, state.Energy);
}

// The UI receives only its own drawn cards; no opponent hand, pile order or
// pending opponent command crosses this boundary.
public sealed record CombatPlayerView(BattleId Battle, long Revision, int ActionValue, CombatPhase Phase,
    PublicCombatantView Self, PublicCombatantView Opponent, IReadOnlyList<CardInstance> OwnCards, bool CanAct)
{
    private static readonly HashSet<string> PublicEvents = new(StringComparer.Ordinal)
    {
        "CardPlayed", "DeckShuffled", "PoisonDamage", "PoisonExtraDamage", "PoisonDecayRetained",
        "PoisonDecayPrevented", "PoisonDecay", "Fatigue", "AutomaticShieldExecute", "ActiveShieldBurst",
        "WindTraceExplosion", "MainMissile", "Submissile", "TideSpent", "WindGaleTrueShot",
        "ConditionalMissileHealing", "EmberSpent", "EmberGenerated", "WindSubmissile", "EarthReflect",
        "PoisonApplied", "ShieldBreakReturn", "BattleFinished", "TimeRewind"
    };

    public static CombatPlayerView? Create(BattleInstance instance, PlayerId viewer)
    {
        if (instance.Pairing.PlayerA != viewer && instance.Pairing.PlayerB != viewer) return null;
        var state = instance.State;
        var self = state.A.Player == viewer ? state.A : state.B;
        var opponent = state.A.Player == viewer ? state.B : state.A;
        return new(state.Battle, state.Revision, state.ActionValue, state.Phase,
            PublicCombatantView.From(self), PublicCombatantView.From(opponent), self.CurrentPool.ToArray(),
            state.Phase == CombatPhase.Decision && !state.EndedWindows.Contains(viewer) &&
            !state.PendingActions.Any(a => a.Player == viewer));
    }

    public static IReadOnlyList<CombatEvent> VisibleEvents(BattleInstance instance, PlayerId viewer, IEnumerable<CombatEvent> events)
    {
        if (instance.Pairing.PlayerA != viewer && instance.Pairing.PlayerB != viewer) return Array.Empty<CombatEvent>();
        return events.Where(e => (e.Player == instance.Pairing.PlayerA || e.Player == instance.Pairing.PlayerB) &&
                (e.Player == viewer || PublicEvents.Contains(e.Kind)))
            .Select(e => e.Player == viewer || e.Kind == "CardPlayed" ? e : e with { CardId = null }).ToArray();
    }
}
