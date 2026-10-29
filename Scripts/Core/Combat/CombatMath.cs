namespace Magicians.Core.Combat;

public static class CombatMath
{
    public static int Ceiling(decimal value) => checked((int)decimal.Ceiling(value));
    public static int Floor(decimal value) => checked((int)decimal.Floor(value));
    public static int AddOrdinaryShield(int oldShield, int gain) => Ceiling(oldShield * 0.75m) + gain;

    // Supported slice has no fire multiplier, defense penetration, vulnerability or mitigation.
    public static int MissileDamage(decimal rawAttack, int defense, int defensePenetrationPercent = 0, int independentDefenseIgnorePercent = 0) =>
        Math.Max(1, Floor(rawAttack - defense * Math.Max(0, 100 - defensePenetrationPercent) / 100m
            * (100 - Math.Clamp(independentDefenseIgnorePercent, 0, 100)) / 100m));

    public static int PoisonDamage(decimal rawDamage, int defense) =>
        Math.Max(1, Floor(rawDamage - defense * 0.5m));

    public static (int Shield, int Life) SplitDamage(int damage, int shield, int windLayers, bool windSpecialized = false, int extraShieldPenetrationPercent = 0)
    {
        var penetration = Math.Min(1m, windLayers * (windSpecialized ? 0.03m : 0.015m) + extraShieldPenetrationPercent / 100m);
        var direct = damage * penetration;
        var over = damage - direct;
        var absorbed = Math.Min(shield, Math.Max(0, Floor(over)));
        var life = Floor(direct + Math.Max(0m, over - absorbed));
        return (absorbed, Math.Max(0, life));
    }

    public static int FatigueLoss(int life, int actionValue) => actionValue < 1500 || life <= 0 ? 0 :
        Math.Max(1, Ceiling(life * (0.05m + actionValue * 0.0001m)));

    public static (int Shield, int Life) SplitShieldBurst(int damage, int shield, int penetrationPercent)
    {
        var direct = Floor(damage * Math.Clamp(penetrationPercent, 0, 100) / 100m);
        var absorbed = Math.Min(shield, Math.Max(0, damage - direct));
        return (absorbed, damage - absorbed);
    }
}
