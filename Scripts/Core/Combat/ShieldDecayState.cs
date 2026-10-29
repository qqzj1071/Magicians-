namespace Magicians.Core.Combat;

/// <summary>Ordinary shield decay since the previous main shot (or activation before
/// the first shot). Includes the current pre-fire gain and resets after firing;
/// it is never a cumulative battle statistic.</summary>
public sealed record ShieldDecayState(bool Active = false, int PendingDamage = 0, int NextBonusPercent = 0)
{
    public ShieldDecayState OnOrdinaryGain(int oldShield)
    {
        if (!Active) return this;
        var lost = Math.Max(0, oldShield - CombatMath.Ceiling(oldShield * 0.75m));
        return this with { PendingDamage = checked(PendingDamage + lost * 3) };
    }

    public int MainDamage => CombatMath.Floor(PendingDamage * (1 + NextBonusPercent / 100m));
    public ShieldDecayState AfterFire() => this with { PendingDamage = 0, NextBonusPercent = 0 };
}
