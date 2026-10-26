namespace Magicians.Core.Combat;

/// <summary>
/// Extension point for effects that intentionally diverge from the default
/// simultaneous snapshot fire rule. The default policy prepares both combatants
/// before either projectile is resolved.
/// </summary>
public interface ICombatResolutionPolicy
{
    CombatantState PrepareBeforeFire(CombatantState state, bool fireDue);
    bool UsesSynchronizedFireSnapshot { get; }
}

public sealed class SnapshotCombatResolutionPolicy : ICombatResolutionPolicy
{
    public bool UsesSynchronizedFireSnapshot => true;

    public CombatantState PrepareBeforeFire(CombatantState state, bool fireDue)
    {
        if (!fireDue) return state;
        if (state.EarthLayers > 0)
        {
            var ratio = state.EarthSpecialized ? 0.04m : 0.02m;
            state = state with
            {
                ShieldDecay = state.ShieldDecay.OnOrdinaryGain(state.Shield),
                Shield = CombatMath.AddOrdinaryShield(state.Shield,
                    CombatMath.Ceiling((state.Attack + state.Defense) * state.EarthLayers * ratio))
            };
        }
        // Temporary shield gains do not decay old shield. Prepare both sides
        // before either outgoing packet so this shield can block same-time hits.
        if (state.NextMainTemporaryShieldPercent > 0)
        {
            var gain = CombatMath.Ceiling(state.Attack * state.NextMainTemporaryShieldPercent / 100m);
            state = state with { Shield = state.Shield + gain, TemporaryShield = state.TemporaryShield + gain,
                NextMainTemporaryShieldPercent = 0 };
        }
        return state;
    }
}
