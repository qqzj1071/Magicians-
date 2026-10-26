namespace Magicians.Core.Combat;

public enum TemporaryTrigger
{
    NextDraw,
    NextFire,
    WindowClosed,
    BattleFinished
}

public sealed record TemporaryEffectDefinition(
    string Id,
    TemporaryTrigger ConsumedAt,
    string Description);

/// <summary>
/// Canonical registry for one-shot and short-lived combat resources. Legacy
/// fields remain in the serialized combat snapshot for compatibility; all new
/// effects should enter through this registry and be consumed by trigger.
/// </summary>
public static class CombatTriggerRegistry
{
    private static readonly IReadOnlyDictionary<string, TemporaryEffectDefinition> Definitions =
        new Dictionary<string, TemporaryEffectDefinition>(StringComparer.Ordinal)
        {
            ["next.damage.percent"] = new("next.damage.percent", TemporaryTrigger.NextFire, "下一发飞弹增伤百分点"),
            ["next.damage.flat"] = new("next.damage.flat", TemporaryTrigger.NextFire, "下一发飞弹固定增伤"),
            ["next.fire.gap"] = new("next.fire.gap", TemporaryTrigger.NextFire, "下一发发射间隔修正"),
            ["battle.interval.modifier"] = new("battle.interval.modifier", TemporaryTrigger.BattleFinished, "本场攻击间隔永久修正"),
            ["battle.interval.multiplier"] = new("battle.interval.multiplier", TemporaryTrigger.BattleFinished, "本场攻击间隔永久乘算百分比"),
            ["next.interval.multiplier"] = new("next.interval.multiplier", TemporaryTrigger.NextFire, "下一发攻击间隔临时乘算百分比"),
            ["next.incoming.damage.multiplier"] = new("next.incoming.damage.multiplier", TemporaryTrigger.NextFire, "下一次承受飞弹伤害乘算百分比"),
            ["next.incoming.damage.flat"] = new("next.incoming.damage.flat", TemporaryTrigger.NextFire, "下一次承受飞弹伤害固定减免"),
            ["battle.healing.reduction"] = new("battle.healing.reduction", TemporaryTrigger.NextDraw, "持续减疗百分比"),
            ["battle.incoming.damage.multiplier"] = new("battle.incoming.damage.multiplier", TemporaryTrigger.NextDraw, "持续易伤百分比"),
            ["next.shield.penetration"] = new("next.shield.penetration", TemporaryTrigger.NextFire, "下一发护盾穿透"),
            ["next.defense.penetration"] = new("next.defense.penetration", TemporaryTrigger.NextFire, "下一发防御穿透"),
            ["next.submissiles"] = new("next.submissiles", TemporaryTrigger.NextFire, "下一发普通副弹数量"),
            ["next.wind.submissiles"] = new("next.wind.submissiles", TemporaryTrigger.NextFire, "下一发风系副弹数量"),
            ["next.wind.flat"] = new("next.wind.flat", TemporaryTrigger.NextFire, "下一发风系副弹固定伤害"),
            ["next.wind.attack.percent"] = new("next.wind.attack.percent", TemporaryTrigger.NextFire, "下一发风系副弹攻击比例"),
            ["next.draw"] = new("next.draw", TemporaryTrigger.NextDraw, "下次抽牌数量"),
            ["next.energy"] = new("next.energy", TemporaryTrigger.NextDraw, "下次抽牌费用"),
            ["temporary.attack.reduction"] = new("temporary.attack.reduction", TemporaryTrigger.NextDraw, "临时攻击削减"),
            ["temporary.defense.reduction"] = new("temporary.defense.reduction", TemporaryTrigger.NextDraw, "临时防御削减"),
            ["temporary.poison"] = new("temporary.poison", TemporaryTrigger.NextDraw, "临时毒层")
        };

    public static IReadOnlyCollection<TemporaryEffectDefinition> All => Definitions.Values.ToArray();

    public static bool IsRegistered(string id) => Definitions.ContainsKey(id);

    public static int Priority(TemporaryTrigger trigger) => trigger switch
    {
        TemporaryTrigger.NextDraw => 10,
        TemporaryTrigger.NextFire => 20,
        TemporaryTrigger.WindowClosed => 30,
        TemporaryTrigger.BattleFinished => 40,
        _ => 100
    };

    public static IReadOnlyList<TemporaryTrigger> OrderedTriggers =>
        Enum.GetValues<TemporaryTrigger>().OrderBy(Priority).ToArray();

    public static CombatResourceState Apply(CombatResourceState state, string id, int amount)
    {
        if (!Definitions.ContainsKey(id))
            throw new KeyNotFoundException($"Unknown temporary combat effect '{id}'.");
        return id switch
        {
            "next.damage.percent" => state with { NextMissileBonusPercent = state.NextMissileBonusPercent + amount },
            "next.damage.flat" => state with { NextMissileBonusFlat = state.NextMissileBonusFlat + amount },
            "next.fire.gap" => state with { NextGapAdjustment = state.NextGapAdjustment + amount },
            "battle.interval.modifier" => state with { AttackIntervalModifier = state.AttackIntervalModifier + amount },
            "battle.interval.multiplier" => state with { PermanentIntervalMultiplierPercent = state.PermanentIntervalMultiplierPercent * amount / 100 },
            "next.interval.multiplier" => state with { TemporaryIntervalMultiplierPercent = state.TemporaryIntervalMultiplierPercent * amount / 100 },
            "next.incoming.damage.multiplier" => state with { NextIncomingDamageMultiplierPercent = state.NextIncomingDamageMultiplierPercent * amount / 100 },
            "next.incoming.damage.flat" => state with { NextIncomingDamageFlat = state.NextIncomingDamageFlat + amount },
            "battle.healing.reduction" => state with { HealingReductionPercent = state.HealingReductionPercent + amount, HealingReductionUntilActionValue = Math.Max(state.HealingReductionUntilActionValue, amount == 0 ? 0 : 100) },
            "battle.incoming.damage.multiplier" => state with { BattleIncomingDamageMultiplierPercent = state.BattleIncomingDamageMultiplierPercent + amount, BattleIncomingDamageUntilActionValue = Math.Max(state.BattleIncomingDamageUntilActionValue, 100) },
            "next.shield.penetration" => state with { NextShieldPenetrationPercent = state.NextShieldPenetrationPercent + amount },
            "next.defense.penetration" => state with { NextDefensePenetrationPercent = state.NextDefensePenetrationPercent + amount },
            "next.submissiles" => state with { PendingSubmissiles = state.PendingSubmissiles + amount },
            "next.wind.submissiles" => state with { PendingWindSubmissiles = state.PendingWindSubmissiles + amount },
            "next.wind.flat" => state with { NextWindSubmissileFlat = state.NextWindSubmissileFlat + amount },
            "next.wind.attack.percent" => state with { NextWindSubmissileAttackPercent = state.NextWindSubmissileAttackPercent + amount },
            "next.draw" => state with { NextDrawBonus = state.NextDrawBonus + amount },
            "next.energy" => state with { NextEnergyBonus = state.NextEnergyBonus + amount },
            "temporary.attack.reduction" => state with { TemporaryAttackReduction = state.TemporaryAttackReduction + amount },
            "temporary.defense.reduction" => state with { TemporaryDefenseReduction = state.TemporaryDefenseReduction + amount },
            "temporary.poison" => state with { TemporaryPoisonLayers = state.TemporaryPoisonLayers + amount },
            _ => state
        };
    }

    public static CombatResourceState Consume(CombatResourceState state, TemporaryTrigger trigger) => trigger switch
    {
        TemporaryTrigger.NextFire => state with
        {
            NextGapAdjustment = 0,
            PendingSubmissiles = 0,
            PendingWindSubmissiles = 0,
            NextWindSubmissileFlat = 0,
            NextWindSubmissileAttackPercent = 0,
            NextMissileBonusPercent = 0,
            NextMissileBonusFlat = 0,
            NextShieldPenetrationPercent = 0,
            NextDefensePenetrationPercent = 0
            ,NextShieldDamageMultiplierPercent = 0
            ,TemporaryIntervalMultiplierPercent = 100
            ,NextIncomingDamageMultiplierPercent = 100
            ,NextIncomingDamageFlat = 0
        },
        TemporaryTrigger.NextDraw => state with { NextDrawBonus = 0, NextEnergyBonus = 0 },
        _ => state
    };

    public static CombatantState Consume(CombatantState state, TemporaryTrigger trigger) => trigger switch
    {
        TemporaryTrigger.NextFire => state with
        {
            NextGapAdjustment = 0,
            PendingSubmissiles = 0,
            PendingWindSubmissiles = 0,
            NextWindSubmissileFlat = 0,
            NextWindSubmissileAttackPercent = 0,
            NextMissileBonusPercent = 0,
            NextMissileBonusFlat = 0,
            NextShieldPenetrationPercent = 0,
            NextDefensePenetrationPercent = 0
            ,NextShieldDamageMultiplierPercent = 0
            ,TemporaryIntervalMultiplierPercent = 100
            ,NextIncomingDamageMultiplierPercent = 100
            ,NextIncomingDamageFlat = 0
        },
        TemporaryTrigger.NextDraw => state with { NextDrawBonus = 0, NextEnergyBonus = 0 },
        _ => state
    };
}
