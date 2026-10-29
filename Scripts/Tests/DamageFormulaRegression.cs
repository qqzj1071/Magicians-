using Magicians.Core.Combat;

namespace Magicians.Tests;

public static class DamageFormulaRegression
{
    public static void Run()
    {
        Require(CombatMath.MissileDamage(100, 20) == 80, "Base missile damage must subtract effective defense.");
        Require(CombatMath.MissileDamage(100, 20, 50) == 90, "Defense penetration must reduce only effective defense.");
        Require(CombatMath.MissileDamage(200, 100, 8, 15) == 121, "Independent defense ignore must multiply the remaining defense after penetration.");
        Require(CombatMath.MissileDamage(5, 20) == 1, "Ordinary missile damage must retain the nonzero floor.");
        Require(CombatMath.PoisonDamage(100, 20) == 90, "Poison must use 50% defense.");
        Require(CombatMath.SplitDamage(100, 50, 0) is (50, 50), "Shield split must absorb before life.");
        Require(CombatMath.SplitDamage(100, 50, 10) is (50, 50), "Shield penetration must split direct and absorbed damage.");
        Require(CombatMath.SplitShieldBurst(100, 40, 50) is (40, 60), "Shield burst penetration must use its own split.");
        Require(CombatMath.FatigueLoss(1000, 1500) == 200, "Fatigue must use the documented ceiling and action-value coefficient.");
        Require(CombatMath.FatigueLoss(1, 1500) == 1, "Fatigue must retain the one-point floor.");
        Godot.GD.Print("DAMAGE_FORMULA_OK missile=OK poison=OK shield-split=OK burst=OK fatigue-ceil=OK");
    }

    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidDataException(message);
    }
}
