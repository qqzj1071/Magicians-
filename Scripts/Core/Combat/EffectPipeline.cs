using Magicians.Core.Cards;
using Magicians.Core.Common;

namespace Magicians.Core.Combat;

/// <summary>Global combat timing order. Lower values always resolve first.</summary>
public enum EffectTiming
{
    BeforePlay = 10,
    OnPlay = 20,
    AfterPlay = 30,
    BeforeDraw = 40,
    AfterDraw = 50,
    BeforeFire = 60,
    ProjectileCreated = 70,
    BeforeShieldSplit = 80,
    AfterShieldSplit = 90,
    AfterDamage = 100,
    AfterFire = 110,
    WindowClosed = 120,
    BattleFinished = 130
}

public sealed record CombatResourceState(
    int Life,
    int Shield,
    int Attack,
    int Defense,
    int Energy,
    int DeckElementCount,
    string PrimaryElement,
    bool ElementForgeActive,
    int ElementForgeBonusLayers,
    int ElementForgePotentialLayers,
    decimal AttackIntervalModifier,
    int PermanentIntervalMultiplierPercent,
    int TemporaryIntervalMultiplierPercent,
    int NextIncomingDamageMultiplierPercent,
    int NextIncomingDamageFlat,
    int TemporaryShield,
    decimal Tides,
    bool TideActive,
    int NextTideDamageMultiplierPercent,
    int TideRefundPercent,
    bool BloodTideActive,
    int NextWaterShieldHealingMultiplierPercent,
    decimal ActualHealingThisBattle,
    int CardsPlayedThisWindow,
    bool GuardianBarrierActive,
    bool WarGodEmblemActive,
    CombatRewindSnapshot? RewindSnapshot,
    int NextPoisonOnHitLayers,
    int NextPoisonOnHitCharges,
    int ExtraPoisonTickCharges,
    bool PlagueLifeDamageActive,
    bool PoisonExplosionActive,
    bool PlagueActive,
    int PlagueAttackReduction,
    int PlagueDefenseReduction,
    int HealingReductionPercent,
    int HealingReductionUntilActionValue,
    int BattleIncomingDamageMultiplierPercent,
    int BattleIncomingDamageUntilActionValue,
    int WindLayers,
    int WaterLayers,
    int EarthLayers,
    bool EarthBarrierActive,
    int ShieldBreakReturnPercent,
    int ShieldBreakReturnFlat,
    bool ShieldBreakDefenseMarkerActive,
    bool ShieldBreakDrawMarkerActive,
    bool ShieldBrokenThisBattle,
    int FireLayers,
    int Embers,
    bool EmberDamageActive,
    bool EmberCoreActive,
    bool AshRebirthUsed,
    bool AshCycleActive,
    int ShuffleCount,
    int TemperBonusUses,
    int PoisonLayers,
    int NextDrawBonus,
    int NextEnergyBonus,
    decimal NextGapAdjustment,
    int PendingSubmissiles,
    int PendingWindSubmissiles,
    int NextWindSubmissileFlat,
    int NextWindSubmissileAttackPercent,
    bool WindTraceActive,
    int WindTraceLayers,
    int WindTraceBonusLayers,
    bool WindGaleActive,
    int WindMainShotCount,
    int WindTraceExplosionMultiplierPercent,
    bool WindArrowActive,
    int NextShieldDamageMultiplierPercent,
    bool WindChaseActive,
    int LastMainMissileActionValue,
    int LastMainMissileActualDamage,
    int MainDamageBonusUntilDrawPercent,
    int NextMissileBonusPercent,
    int NextMissileBonusFlat,
    int NextMissileHealingPercent,
    int NextShieldPenetrationPercent,
    int MainShieldPenetrationUntilDrawPercent,
    int MainDefensePenetrationPercent,
    int NextDefensePenetrationPercent,
    int NextMainTemporaryShieldPercent,

    int BattleAttackReduction,
    int BattleDefenseReduction,
    int NegativeSuppressedUntilActionValue,
    int TemporaryAttackReduction,
    int TemporaryDefenseReduction,
    int TemporaryPoisonLayers,
    int PoisonEnchantmentLayers,
    int NextPoisonDecayActionValue,
    int PoisonDecayIntervalPercent,
    int PoisonDecayProtectionCharges,
    bool PoisonDecayKeepLast,
    bool PoisonSpecialized,
    bool FireSpecialized,
    bool WaterSpecialized,
    bool EarthSpecialized,
    bool WindSpecialized,
    IReadOnlyDictionary<string, int> Counters,
    IReadOnlySet<string> Statuses
)
{
    public int UnredeemedEmbersSpent { get; init; }
    public int AshCyclePendingCredit { get; init; }
    public ShieldDecayState ShieldDecay { get; init; } = new();
    public bool BastionHeartActive { get; init; }
    public bool BurningBloodlineActive { get; init; }
    public bool LifeSpringActive { get; init; }
    public int NextTideHealingRecordBonusPercent { get; init; }

    public static CombatResourceState From(CombatantState state) => new(
        state.Life, state.Shield, state.Attack, state.Defense, state.Energy, state.DeckElementCount, state.PrimaryElement,
        state.ElementForgeActive, state.ElementForgeBonusLayers, state.ElementForgePotentialLayers, state.AttackIntervalModifier,
        state.PermanentIntervalMultiplierPercent, state.TemporaryIntervalMultiplierPercent,
        state.NextIncomingDamageMultiplierPercent, state.NextIncomingDamageFlat,
        state.TemporaryShield, state.Tides, state.TideActive, state.NextTideDamageMultiplierPercent,
        state.TideRefundPercent, state.BloodTideActive, state.NextWaterShieldHealingMultiplierPercent,
        state.ActualHealingThisBattle, state.CardsPlayedThisWindow, state.GuardianBarrierActive, state.WarGodEmblemActive,
        state.RewindSnapshot,
        state.NextPoisonOnHitLayers, state.NextPoisonOnHitCharges, state.ExtraPoisonTickCharges, state.PlagueLifeDamageActive, state.PoisonExplosionActive,
        state.PlagueActive, state.PlagueAttackReduction, state.PlagueDefenseReduction,
        state.HealingReductionPercent, state.HealingReductionUntilActionValue,
        state.BattleIncomingDamageMultiplierPercent, state.BattleIncomingDamageUntilActionValue,
        state.WindLayers, state.WaterLayers, state.EarthLayers, state.EarthBarrierActive, state.ShieldBreakReturnPercent, state.ShieldBreakReturnFlat,
        state.ShieldBreakDefenseMarkerActive, state.ShieldBreakDrawMarkerActive, state.ShieldBrokenThisBattle,
        state.FireLayers, state.Embers, state.EmberDamageActive, state.EmberCoreActive, state.AshRebirthUsed, state.AshCycleActive, state.ShuffleCount, state.TemperBonusUses, state.PoisonLayers,
        state.NextDrawBonus, state.NextEnergyBonus, state.NextGapAdjustment, state.PendingSubmissiles,
        state.PendingWindSubmissiles, state.NextWindSubmissileFlat, state.NextWindSubmissileAttackPercent,
        state.WindTraceActive, state.WindTraceLayers, state.WindTraceBonusLayers, state.WindGaleActive, state.WindMainShotCount,
        state.WindTraceExplosionMultiplierPercent, state.WindArrowActive, state.NextShieldDamageMultiplierPercent,
        state.WindChaseActive, state.LastMainMissileActionValue, state.LastMainMissileActualDamage,
        state.MainDamageBonusUntilDrawPercent,
        state.NextMissileBonusPercent,
        state.NextMissileBonusFlat, state.NextMissileHealingPercent, state.NextShieldPenetrationPercent, state.MainShieldPenetrationUntilDrawPercent, state.MainDefensePenetrationPercent, state.NextDefensePenetrationPercent, state.NextMainTemporaryShieldPercent,
        state.BattleAttackReduction, state.BattleDefenseReduction, state.NegativeSuppressedUntilActionValue,
        state.TemporaryAttackReduction, state.TemporaryDefenseReduction, state.TemporaryPoisonLayers,
        state.PoisonEnchantmentLayers, state.NextPoisonDecayActionValue,
        state.PoisonDecayIntervalPercent, state.PoisonDecayProtectionCharges, state.PoisonDecayKeepLast,
        state.PoisonSpecialized, state.FireSpecialized, state.WaterSpecialized,
        state.EarthSpecialized, state.WindSpecialized,
        new Dictionary<string, int>(StringComparer.Ordinal),
        new HashSet<string>(StringComparer.Ordinal))
        { UnredeemedEmbersSpent = state.UnredeemedEmbersSpent, AshCyclePendingCredit = state.AshCyclePendingCredit, ShieldDecay = state.ShieldDecay, BastionHeartActive = state.BastionHeartActive, BurningBloodlineActive = state.BurningBloodlineActive, LifeSpringActive = state.LifeSpringActive, NextTideHealingRecordBonusPercent = state.NextTideHealingRecordBonusPercent };
}

public sealed record EffectContext(
    BattleId Battle,
    int ActionValue,
    PlayerId Source,
    PlayerId Target,
    CardInstance? Card,
    CombatResourceState SourceResources,
    CombatResourceState TargetResources
);

public sealed class BasicImmediateEffectResolver : ICardEffectResolver
{
    public BasicImmediateEffectResolver(string cardId) => CardId = cardId;
    public string CardId { get; }

    public IReadOnlyList<EffectMutation> Resolve(EffectContext context, EffectTiming timing)
    {
        if (timing != EffectTiming.OnPlay) return Array.Empty<EffectMutation>();
        var source = context.SourceResources;
        var target = context.TargetResources;
        switch (CardId)
        {
            case "护盾": source = source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 60) }; break;
            case "石肤": source = source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 50) }; break;
            case "包扎": source = source with { Life = Math.Min(1000, source.Life + 25) }; break;
            case "小治疗": source = source with { Life = Math.Min(1000, source.Life + 40) }; break;
            case "小盾": source = source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 50) }; break;
            case "水滴": source = source with { Life = Math.Min(1000, source.Life + 30) }; break;
            case "水膜": source = source with { Life = Math.Min(1000, source.Life + 20) }; break;
            case "毒甲": source = source with
            { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 30), PoisonEnchantmentLayers = source.PoisonEnchantmentLayers + 1 }; break;
            case "坚岩":
                source = source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 50) };
                if (source.Shield >= 100) source = source with { Defense = source.Defense + 2 };
                break;
            case "岩甲":
                source = source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 70) };
                if (source.Shield >= 100) source = source with { Attack = source.Attack + 2 };
                break;
            case "速读": source = CombatTriggerRegistry.Apply(source, "next.draw", 1); break;
            case "鼓舞": source = CombatTriggerRegistry.Apply(source, "next.energy", 1); break;
            case "整理": source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.draw", 2), "next.energy", -1); break;
            case "循环": source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.draw", 1), "next.energy", 1); break;
            case "短促": source = CombatTriggerRegistry.Apply(source, "next.fire.gap", -7.5m); break;
            case "微风": source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.submissiles", 1), "next.wind.flat", 15), "next.wind.attack.percent", 20); break;
            case "蓄能": source = CombatTriggerRegistry.Apply(source, "next.damage.percent", 14); break;
            case "疾风": source = CombatTriggerRegistry.Apply(source, "next.wind.submissiles", 1); break;
            case "穿甲":
                source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.wind.submissiles", 1), "next.wind.flat", 22), "next.wind.attack.percent", 20);
                source = CombatTriggerRegistry.Apply(source, "next.fire.gap", -5);
                target = target with { Defense = Math.Max(0, target.Defense - 3), BattleDefenseReduction = target.BattleDefenseReduction + 3 }; break;
            case "穿云": source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.wind.submissiles", 1), "next.wind.flat", 25), "next.wind.attack.percent", 30); break;
            case "穿云破甲":
                source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.wind.submissiles", 1), "next.wind.flat", 35), "next.wind.attack.percent", 25);
                source = CombatTriggerRegistry.Apply(source, "battle.interval.modifier", -1);
                target = target with { Defense = Math.Max(0, target.Defense - 4), BattleDefenseReduction = target.BattleDefenseReduction + 4 }; break;
            case "风暴": source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.wind.submissiles", 1), "next.wind.flat", 30), "next.wind.attack.percent", 30); break;
            case "风驰": source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.wind.submissiles", 1), "next.wind.flat", 12), "next.wind.attack.percent", 30); break;
            case "风痕刻印":
                source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.wind.submissiles", 1), "next.wind.flat", 15), "next.wind.attack.percent", 15);
                source = source.WindTraceActive ? source with { WindTraceBonusLayers = source.WindTraceBonusLayers + 2 } : CombatTriggerRegistry.Apply(source, "next.fire.gap", -5);
                break;
            case "风卷": source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.wind.submissiles", 1), "next.wind.flat", 25), "next.wind.attack.percent", 25); break;
            case "风切": source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.wind.submissiles", 1), "next.wind.flat", 15), "next.wind.attack.percent", 15); break;
            case "风牙": source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.wind.submissiles", 1), "next.wind.flat", 10), "next.wind.attack.percent", 15); break;
            case "疾行": source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.wind.submissiles", 1), "next.wind.flat", 18), "next.wind.attack.percent", 15); source = CombatTriggerRegistry.Apply(source, "next.fire.gap", -10); break;
            case "裂风": source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.wind.submissiles", 1), "next.wind.flat", 22), "next.wind.attack.percent", 20); break;
            case "破风":
                source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.wind.submissiles", 1), "next.wind.flat", 18), "next.wind.attack.percent", 20);
                target = target with { Defense = Math.Max(0, target.Defense - 2), BattleDefenseReduction = target.BattleDefenseReduction + 2 }; break;
            case "顺风": source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.wind.submissiles", 1), "next.wind.flat", 12), "next.wind.attack.percent", 25), "battle.interval.modifier", -1m); break;
            case "追风": source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.wind.submissiles", 1), "next.wind.flat", 15), "next.wind.attack.percent", 35), "battle.interval.modifier", -0.5m); break;
            case "追云": source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.wind.submissiles", 1), "next.wind.flat", 12), "next.wind.attack.percent", 25); source = CombatTriggerRegistry.Apply(source, "next.fire.gap", -7.5m); break;
            case "风神之翼": source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.wind.submissiles", 1), "next.wind.flat", 20), "next.wind.attack.percent", 30), "battle.interval.modifier", -1m); break;
            case "风蚀":
                source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.wind.submissiles", 1), "next.wind.flat", 25), "next.wind.attack.percent", 25);
                target = target with { Defense = Math.Max(0, target.Defense - 4), BattleDefenseReduction = target.BattleDefenseReduction + 4 }; break;
            case "风痕": source = source with { WindTraceActive = true }; break;
            case "天岚": source = source with { WindGaleActive = true, WindMainShotCount = 0 }; break;
            case "裂空": source = CombatTriggerRegistry.Apply(source with { WindTraceExplosionMultiplierPercent = source.WindTraceExplosionMultiplierPercent + 50 }, "battle.interval.modifier", -1m); break;
            case "疾风连斩": source = CombatTriggerRegistry.Apply(source, "battle.interval.modifier", -1m); break;
            case "疾风之刃": source = source with { WindChaseActive = true, LastMainMissileActionValue = -1, LastMainMissileActualDamage = 0 }; break;
            case "疾影": source = source with { MainDamageBonusUntilDrawPercent = 25 }; break;
            case "穿云箭": source = source with { WindArrowActive = true }; break;
            case "裂空穿云":
                target = target with { Defense = Math.Max(0, target.Defense - 4), BattleDefenseReduction = target.BattleDefenseReduction + 4 };
                source = CombatTriggerRegistry.Apply(source, "next.shield.penetration", 0) with { NextShieldDamageMultiplierPercent = source.NextShieldDamageMultiplierPercent + 30 };
                break;
            case "风步": source = CombatTriggerRegistry.Apply(source, "next.fire.gap", -7.5m); break;
            case "风幕":
                source = CombatTriggerRegistry.Apply(source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 60) }, "next.fire.gap", -10);
                target = target with { ShieldDecay = target.ShieldDecay.OnOrdinaryGain(target.Shield), Shield = CombatMath.AddOrdinaryShield(target.Shield, 60) };
                break;
            case "气旋护壁":
                source = source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 100) };
                target = target with { ShieldDecay = target.ShieldDecay.OnOrdinaryGain(target.Shield), Shield = CombatMath.AddOrdinaryShield(target.Shield, 100) };
                source = CombatTriggerRegistry.Apply(source, "battle.interval.modifier", -1m);
                break;
            case "风痕回廊":
                source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.wind.submissiles", 2), "next.wind.flat", 15), "next.wind.attack.percent", 15);
                if (source.WindTraceActive) source = source with { WindTraceBonusLayers = source.WindTraceBonusLayers + 1 };
                break;
            case "威吓":
            case "削弱":
                if (context.TargetResources.NegativeSuppressedUntilActionValue > context.ActionValue)
                    return new[] { new EffectMutation(CardId, timing, 0, source, context.TargetResources, Array.Empty<CombatEvent>()) };
                return new[] { new EffectMutation(CardId, timing, 0, source,
                    context.TargetResources with
                    {
                        Attack = context.TargetResources.Attack - 2,
                        BattleAttackReduction = context.TargetResources.BattleAttackReduction + 2
                    }, Array.Empty<CombatEvent>()) };
            case "破甲":
                if (context.TargetResources.NegativeSuppressedUntilActionValue > context.ActionValue)
                    return new[] { new EffectMutation(CardId, timing, 0, source, context.TargetResources, Array.Empty<CombatEvent>()) };
                return new[] { new EffectMutation(CardId, timing, 0, source,
                    context.TargetResources with
                    {
                        Defense = context.TargetResources.Defense - 4,
                        BattleDefenseReduction = context.TargetResources.BattleDefenseReduction + 4
                    }, Array.Empty<CombatEvent>()) };
            case "火墙":
                if (source.BattleAttackReduction == 0 && source.BattleDefenseReduction == 0 &&
                    source.TemporaryAttackReduction == 0 && source.TemporaryDefenseReduction == 0 && source.PoisonLayers == 0 && source.TemporaryPoisonLayers == 0)
                    source = source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 20) };
                else
                    source = ClearNegative(source, Math.Max(0, source.PoisonLayers - 1));
                break;
            case "应急整备":
                source = CombatTriggerRegistry.Apply(
                    ClearNegative(source, Math.Max(0, source.PoisonLayers - 2)) with { Life = Math.Min(1000, source.Life + 100) },
                    "next.draw", 1);
                break;
            case "风之躯":
                source = ClearNegative(source, 0);
                break;
            case "风眼":
                source = source with { NegativeSuppressedUntilActionValue = context.ActionValue + 100 };
                break;
            case "毒涌":
            {
                var consumed = Math.Min(2, source.PoisonLayers);
                source = CombatTriggerRegistry.Apply(
                    CombatTriggerRegistry.Apply(source with { PoisonLayers = source.PoisonLayers - consumed }, "next.draw", consumed),
                    "next.fire.gap", -7.5m);
                break;
            }
            case "延毒": source = source with { PoisonDecayIntervalPercent = source.PoisonDecayIntervalPercent + 15 }; break;
            case "固毒": source = source with { PoisonDecayProtectionCharges = source.PoisonDecayProtectionCharges + 1 }; break;
            case "蚀骨": source = source with { PoisonDecayIntervalPercent = source.PoisonDecayIntervalPercent + 100, PoisonDecayKeepLast = true }; break;
            case "不周山": source = source with { EarthBarrierActive = true }; break;
            case "反震岩核": source = source with { EarthBarrierActive = true, ShieldBreakReturnPercent = source.ShieldBreakReturnPercent + 40 }; break;
            case "回震岩甲": source = source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 150), ShieldBreakReturnFlat = source.ShieldBreakReturnFlat + 60 }; break;
            case "焚心":
            {
                var consumed = Math.Min(2, source.Embers);
                source = consumed > 0
                    ? source with { Embers = source.Embers - consumed, Life = Math.Min(1000, source.Life + CombatMath.Ceiling((1000 - source.Life) * consumed * 0.15m)) }
                    : source with { Embers = source.Embers + 1 };
                break;
            }
            case "余烬之核": source = source with { EmberCoreActive = true }; break;
            case "灰烬循环": source = source with { AshCycleActive = true }; break;
            case "壁垒之心": source = source with { BastionHeartActive = true, NextEnergyBonus = source.NextEnergyBonus + 1 }; break;
            case "不动如山": if (source.Shield >= 50) source = source with { Defense = source.Defense + 2 }; break;
            case "壁障": if (source.Shield >= 30) source = source with { Defense = source.Defense + 2 }; break;
            case "大地之握": source = source with { ShieldDecay = source.ShieldDecay with { Active = true } }; break;
            case "握盾": source = source with { ShieldDecay = source.ShieldDecay with { NextBonusPercent = source.ShieldDecay.NextBonusPercent + 100 } }; break;
            case "灰烬账本":
                source = source.UnredeemedEmbersSpent >= 3
                    ? source with { UnredeemedEmbersSpent = source.UnredeemedEmbersSpent - 3, Embers = source.Embers + 1 }
                    : CombatTriggerRegistry.Apply(source, "next.draw", 2);
                break;
            case "烈焰附身":
                target = target with
                {
                    HealingReductionPercent = Math.Min(100, target.HealingReductionPercent + 25),
                    HealingReductionUntilActionValue = context.ActionValue + 100
                };
                break;
            case "燃烧血统":
                source = source with
                {
                    BurningBloodlineActive = true
                };
                break;
            case "裂岩护壁":
            {
                var shield = source.ShieldBrokenThisBattle ? 110 : 80;
                source = source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, shield) };
                if (source.Shield >= 100)
                    source = source with { Defense = source.Defense + 4 };
                break;
            }
            case "渗骨毒素":
                source = source with { MainShieldPenetrationUntilDrawPercent = source.MainShieldPenetrationUntilDrawPercent + 20 };
                break;
            case "生命之泉":
                source = source with
                {
                    LifeSpringActive = true,
                    MainDefensePenetrationPercent = source.MainDefensePenetrationPercent + 20
                };
                break;
            case "焰心屏障":
                source = source with { NextMainTemporaryShieldPercent = 50 };
                break;
            case "灼痛": source = source with { NextMissileHealingPercent = 5 }; break;
            case "炽焰王冠": source = source with { EmberDamageActive = true }; break;
            case "余火": source = CombatTriggerRegistry.Apply(source, "next.draw", 1); break;
            case "余烬刻度":
                source = source.FireLayers >= 6
                    ? source with { Embers = source.Embers + 1 }
                    : CombatTriggerRegistry.Apply(source, "next.draw", 1);
                break;
            case "火花": source = CombatTriggerRegistry.Apply(source, "next.damage.percent", 9); break;
            case "烈焰冲刺": source = CombatTriggerRegistry.Apply(source, "next.fire.gap", -10); break;
            case "猛火弹": source = CombatTriggerRegistry.Apply(source, "next.damage.percent", 27); break;
            case "压实火药": source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.fire.gap", 30), "next.damage.percent", 16); break;
            case "高压弹仓": source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source with { Embers = source.Embers + 1 }, "next.fire.gap", 30), "next.damage.percent", 14); break;
            case "导火索": source = CombatTriggerRegistry.Apply(source, "next.damage.percent", source.NextGapAdjustment >= 75 ? 16 : 8); break;
            case "慢燃": source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.fire.gap", 50), "next.damage.percent", 30); break;
            case "燃血": source = source with { Life = Math.Max(1, source.Life - CombatMath.Ceiling(source.Life * 0.05m)), Embers = source.Embers + 1 };
                source = CombatTriggerRegistry.Apply(source, "next.draw", 1); break;
            case "余烬心脏":
                source = source.Life <= 300
                    ? source with { Embers = source.Embers + 2, Life = Math.Min(1000, source.Life + CombatMath.Ceiling((1000 - source.Life) * 0.20m)) }
                    : CombatTriggerRegistry.Apply(source with { Embers = source.Embers + 1 }, "next.draw", 1);
                break;
            case "清泉": source = source with { Life = Math.Min(1000, source.Life + 20) }; break;
            case "泉眼": source = source with { Life = Math.Min(1000, source.Life + (source.Life <= 500 ? 50 : 20)) }; break;
            case "涌泉": source = source with { Life = Math.Min(1000, source.Life + 65) }; break;
            case "潮声": source = CombatTriggerRegistry.Apply(source with { Life = Math.Min(1000, source.Life + 25) }, "next.damage.percent", 9); break;
            case "潮涌": source = CombatTriggerRegistry.Apply(source with { Life = Math.Min(1000, source.Life + 35) }, "next.damage.percent", 23); break;
            case "疾流": source = CombatTriggerRegistry.Apply(source, "next.fire.gap", -10); break;
            case "穿潮": source = CombatTriggerRegistry.Apply(source, "next.defense.penetration", 40); break;
            case "水幕": source = CombatTriggerRegistry.Apply(source with { WaterLayers = source.WaterLayers + 1, Life = Math.Min(1000, source.Life + 50) }, "next.shield.penetration", 55); break;
            case "翻阅": source = CombatTriggerRegistry.Apply(source, "next.draw", 1); break;
            case "通晓": source = CombatTriggerRegistry.Apply(source, "next.draw", 2); break;
            case "灵感涌现": source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.draw", 2), "next.energy", 1); break;
            case "愈合之光": source = source with { Life = Math.Min(1000, source.Life + (source.Life <= 500 ? 110 : 70)) }; break;
            case "治愈洪流": source = source with { Life = Math.Min(1000, source.Life + 100) }; break;
            case "盾之共鸣":
            {
                var bonus = source.Shield >= 100 ? 50 : 0;
                source = source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 100 + bonus) };
                break;
            }
            case "锋刃": if (source.Attack >= 70) source = source with { Attack = source.Attack + 3 }; break;
            case "恐惧":
                target = target with { Attack = Math.Max(0, target.Attack - 4), Defense = Math.Max(0, target.Defense - 2), BattleAttackReduction = target.BattleAttackReduction + 4, BattleDefenseReduction = target.BattleDefenseReduction + 2 };
                break;
            case "狂战": if (source.Life <= 500) source = source with { Attack = source.Attack + 6 }; break;
            case "战意沸腾": if (source.Life >= 500) source = source with { Attack = source.Attack + 4 }; break;
            case "铁壁": if (source.Shield >= 50) source = source with { Defense = source.Defense + 3 }; break;
            case "裂伤": target = CombatTriggerRegistry.Apply(target, "next.damage.percent", 45); break;
            case "蓄势": source = CombatTriggerRegistry.Apply(source, "next.damage.percent", 18); break;
            case "战术大师": source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.energy", 1), "next.damage.percent", 18); break;
            case "稳固结界": target = CombatTriggerRegistry.Apply(target, "next.incoming.damage.multiplier", 70); break;
            case "镜岩之心":
                source = source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 60) };
                source = CombatTriggerRegistry.Apply(source, "next.incoming.damage.multiplier", 70);
                break;
            case "守岩":
                source = source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 100) };
                source = CombatTriggerRegistry.Apply(source, "next.incoming.damage.flat", 20);
                break;
            case "临时壁垒": source = source with { Shield = source.Shield + 150, TemporaryShield = source.TemporaryShield + 150 }; break;
            case "岩潮壁垒": source = source with { Shield = source.Shield + 220, TemporaryShield = source.TemporaryShield + 220 }; break;
            case "断流封印":
                target = target with
                {
                    HealingReductionPercent = Math.Min(100, target.HealingReductionPercent + 30),
                    HealingReductionUntilActionValue = context.ActionValue + 100
                };
                break;
            case "回岩":
                source = source with
                {
                    ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 120),
                    BattleIncomingDamageMultiplierPercent = source.BattleIncomingDamageMultiplierPercent + 25,
                    BattleIncomingDamageUntilActionValue = context.ActionValue + 100
                };
                target = target with
                {
                    BattleIncomingDamageMultiplierPercent = target.BattleIncomingDamageMultiplierPercent + 23,
                    BattleIncomingDamageUntilActionValue = context.ActionValue + 100
                };
                break;
            case "碎岳之心":
                source = source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 160) };
                target = target with
                {
                    BattleIncomingDamageMultiplierPercent = target.BattleIncomingDamageMultiplierPercent + 30,
                    BattleIncomingDamageUntilActionValue = context.ActionValue + 100
                };
                break;
            case "潮汐之心": source = source with { TideActive = true }; break;
            case "潮汐回廊":
                source = source with { Life = Math.Min(1000, source.Life + CombatMath.Ceiling(source.Tides * 2m)), Tides = 0m };
                break;
            case "潮汐回响": source = source with { TideActive = true, TideRefundPercent = 25 }; break;
            case "回响之潮": source = CombatTriggerRegistry.Apply(source with { Life = Math.Min(1000, source.Life + 100) }, "next.damage.percent", 0) with { NextTideDamageMultiplierPercent = source.TideActive ? source.NextTideDamageMultiplierPercent + 40 : source.NextTideDamageMultiplierPercent, NextTideHealingRecordBonusPercent = source.TideActive ? source.NextTideHealingRecordBonusPercent + 50 : source.NextTideHealingRecordBonusPercent }; break;
            case "潮汐风暴": source = source with { Life = Math.Min(1000, source.Life + 85), NextTideDamageMultiplierPercent = source.TideActive ? source.NextTideDamageMultiplierPercent + 70 : source.NextTideDamageMultiplierPercent }; break;
            case "血潮": source = source with { BloodTideActive = true }; break;
            case "静水": source = source with { NextWaterShieldHealingMultiplierPercent = 300 }; break;
            case "奔流": source = CombatTriggerRegistry.Apply(source, "battle.interval.multiplier", 90); break;
            case "禁忌知识":
                source = source with { Life = Math.Max(1, source.Life - CombatMath.Ceiling(source.Life * 0.05m)) };
                source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.draw", 3), "next.energy", 1);
                break;
            case "魔力契约": break; // Persistent effect is tracked by the combat authority.
            case "爆裂弹头": source = CombatTriggerRegistry.Apply(source, "next.damage.percent", 18); break;
            case "压缩爆燃":
            {
                var bonus = 10 + (source.Attack >= 90 ? 20 : 0) + (source.FireSpecialized && source.Embers >= 2 ? 15 : 0);
                source = CombatTriggerRegistry.Apply(source, "next.damage.percent", CombatMath.Ceiling(bonus));
                break;
            }
            case "守护者壁垒": source = source with { GuardianBarrierActive = true }; break;
            case "战神徽记": source = source with { WarGodEmblemActive = true }; break;
            case "战意": if (source.FireLayers >= 6) source = source with { Attack = source.Attack + 4 }; break;
            case "高温炉心": if (source.FireLayers >= 6) source = source with { Attack = source.Attack + 4 }; break;
            case "魔法阵核心":
                if (source.DeckElementCount >= 3)
                {
                    var extra = source.DeckElementCount - 2;
                    source = source with
                    {
                        Attack = CombatMath.Floor(source.Attack * (1 + extra * 0.10m)),
                        Defense = CombatMath.Floor(source.Defense * (1 + extra * 0.05m))
                    };
                }
                break;
            case "元素熔炉":
                if (!source.ElementForgeActive && source.ElementForgePotentialLayers > 0)
                {
                    source = source with { ElementForgeActive = true, ElementForgeBonusLayers = source.ElementForgePotentialLayers };
                    source = source.PrimaryElement switch
                    {
                        "fire" => source with { FireLayers = source.FireLayers + source.ElementForgePotentialLayers },
                        "water" => source with { WaterLayers = source.WaterLayers + source.ElementForgePotentialLayers },
                        "earth" => source with { EarthLayers = source.EarthLayers + source.ElementForgePotentialLayers },
                        "wind" => source with { WindLayers = source.WindLayers + source.ElementForgePotentialLayers },
                        "poison" => source with { PoisonEnchantmentLayers = source.PoisonEnchantmentLayers + source.ElementForgePotentialLayers },
                        _ => source
                    };
                }
                break;
            case "时光倒流":
                source = source with
                {
                    RewindSnapshot = new CombatRewindSnapshot(
                        source.Life, source.Attack, source.Defense, source.Shield,
                        source.WindLayers, source.WaterLayers, source.EarthLayers, source.FireLayers,
                        source.Embers, source.EmberDamageActive,
                        source.EarthBarrierActive, source.ShieldBreakReturnPercent, source.ShieldBreakReturnFlat,
                        source.AttackIntervalModifier, source.PermanentIntervalMultiplierPercent,
                        source.WindTraceActive, source.WindGaleActive, source.WindArrowActive,
                        source.WindChaseActive, source.TideActive, source.TideRefundPercent,
                        context.ActionValue, context.ActionValue + 200)
                        { ShieldDecayActive = source.ShieldDecay.Active, BastionHeartActive = source.BastionHeartActive, BurningBloodlineActive = source.BurningBloodlineActive, LifeSpringActive = source.LifeSpringActive }
                };
                break;
            case "毒针":
                if (target.Shield > 0 && target.PoisonLayers == 0)
                {
                    target = target with { PoisonLayers = 1 };
                    if (source.PoisonExplosionActive) source = source with { Attack = source.Attack + 1 };
                }
                break;
            case "毒囊": source = CombatTriggerRegistry.Apply(source, "next.fire.gap", -10); break;
            case "枯潮":
                if (target.PoisonLayers > 0)
                {
                    target = target with { PoisonLayers = target.PoisonLayers + 1 };
                    if (source.PoisonExplosionActive) source = source with { Attack = source.Attack + 1 };
                }
                break;
            case "蚀刻":
                target = ApplyImmediatePoisonDamage(source, target, 1m);
                break;
            case "万蚀":
                target = ApplyImmediatePoisonDamage(source, target, 2m);
                break;
            case "毒爆弹":
                if (source.PoisonExplosionActive) source = source with { Attack = source.Attack + target.PoisonLayers };
                target = ApplyPoisonBurst(source, target, 1.5m);
                source = CombatTriggerRegistry.Apply(source, "next.fire.gap", 0);
                break;
            case "毒潮":
                if (source.PoisonExplosionActive) source = source with { Attack = source.Attack + target.PoisonLayers };
                source = CombatTriggerRegistry.Apply(source, "next.fire.gap", -Math.Min(10, target.PoisonLayers));
                target = ApplyPoisonBurst(source, target, 2.5m);
                break;
            case "万毒爆":
                if (source.PoisonExplosionActive) source = source with { Attack = source.Attack + target.PoisonLayers };
                source = CombatTriggerRegistry.Apply(source, "next.fire.gap", -10);
                target = ApplyPoisonBurst(source, target, 2m);
                break;
            case "疫病":
                source = CombatTriggerRegistry.Apply(source, "next.damage.flat", 40);
                target = target with { Defense = Math.Max(0, target.Defense - 2), BattleDefenseReduction = target.BattleDefenseReduction + 2 };
                break;
            case "盾脉": source = source with { Shield = source.Shield + 140 }; break;
            case "碎石击": source = source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 30) }; break;
            case "碎盾术": source = source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 60) }; break;
            case "磐岩壁":
                source = source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 80) };
                if (source.Shield >= 150) source = source with { Attack = source.Attack + 3 };
                break;
            case "厚土":
                source = Heal(source, Math.Min(150, CombatMath.Floor(source.Shield * 0.40m)));
                break;
            case "山岳之躯":
            {
                var consumed = Math.Min(250, source.Shield);
                source = Heal(source with { Shield = source.Shield - consumed }, consumed * 2);
                break;
            }
            case "速腐": source = source with { NextPoisonOnHitLayers = 2, NextPoisonOnHitCharges = 1 }; break;
            case "腐息": source = source with { ExtraPoisonTickCharges = source.ExtraPoisonTickCharges + 1 }; break;
            case "蚀界":
                target = ApplyImmediatePoisonDamage(source, target, 1m);
                source = source with { NextPoisonOnHitLayers = 1, NextPoisonOnHitCharges = 2 };
                break;
            case "蚀命": source = source with { PlagueLifeDamageActive = true }; break;
            case "毒爆": source = source with { PoisonExplosionActive = true }; break;
            case "万毒之源": source = source with { PlagueActive = true }; break;
            case "岩核重压":
            {
                var defenseRate = 0.50m;
                var raw = CombatMath.Ceiling(Math.Max(0, source.Shield * 0.25m - target.Defense * defenseRate)
                    * (1 + source.FireLayers * (source.FireSpecialized ? 0.02m : 0.01m)));
                var split = CombatMath.SplitShieldBurst(raw, target.Shield,
                    0);
                target = target with { Shield = target.Shield - split.Shield, Life = target.Life - split.Life };
                break;
            }
            case "碎岩印记": source = source with { ShieldBreakDefenseMarkerActive = true }; break;
            case "余震": source = source with { ShieldBreakDrawMarkerActive = true }; break;
            case "濒死回响":
            {
                var payment = Math.Max(1, CombatMath.Ceiling(source.Life * 0.08m));
                var next = source with { Life = Math.Max(1, source.Life - payment) };
                next = CombatTriggerRegistry.Apply(next with { Life = Math.Min(1000, next.Life + 60) }, "next.damage.percent", 27);
                if (next.TideActive) next = next with { Tides = next.Tides + payment * 0.03m * next.WaterLayers };
                source = next;
                break;
            }
            case "血之回响":
            {
                var payment = Math.Max(1, CombatMath.Ceiling(source.Life * 0.10m));
                var next = source with { Life = Math.Max(1, source.Life - payment) };
                next = next with { Life = Math.Min(1000, next.Life + CombatMath.Ceiling((1000 - next.Life) * 0.10m)) };
                if (next.Life <= 300) next = CombatTriggerRegistry.Apply(next, "next.damage.percent", 30);
                if (next.TideActive) next = next with { Tides = next.Tides + payment * 0.05m * next.WaterLayers };
                source = next;
                break;
            }
            case "血刃":
            {
                var payment = Math.Max(1, CombatMath.Ceiling(source.Life * 0.04m));
                source = source with { Life = Math.Max(1, source.Life - payment), Attack = source.Attack + 10 };
                if (source.TideActive) source = source with { Tides = source.Tides + payment * 0.05m * source.WaterLayers };
                break;
            }
            case "血怒":
                if (source.Life <= 500) source = source with { Attack = source.Attack + 8 };
                if (source.TideActive) source = source with { Tides = source.Tides + (1000 - source.Life) * 0.003m * source.WaterLayers };
                break;
            case "血潮汹涌":
                if (source.Life <= 350) source = source with { Attack = source.Attack + 8 };
                if (source.TideActive) source = source with { Tides = source.Tides + (1000 - source.Life) * 0.003m * source.WaterLayers };
                break;
            case "细流": source = CombatTriggerRegistry.Apply(source with { Life = Math.Min(1000, source.Life + 8) }, "next.damage.percent", 9); break;
            case "连环潮": source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.fire.gap", -15), "next.damage.percent", 14); break;
            case "回潮": if (source.ActualHealingThisBattle > 0m) source = source with { Attack = source.Attack + 4 }; break;
            case "回流":
                source = CombatTriggerRegistry.Apply(source, "next.draw", 1);
                if (source.NextGapAdjustment <= -15) source = source with { Attack = source.Attack + 3 };
                break;
            case "潮汐恩泽": source = Heal(source with { WaterLayers = source.WaterLayers + 1 }, 60); break;
            case "血偿": source = source with { Life = Math.Min(1000, source.Life + CombatMath.Ceiling((1000 - source.Life) * 0.06m)) }; break;
            case "泉心": source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.fire.gap", -25), "next.defense.penetration", 60); break;
            case "生命洪流": source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source with { Life = Math.Min(1000, source.Life + 70) }, "next.fire.gap", -15), "next.damage.percent", 17); break;
            case "余烬护心":
                source = source.Embers > 0
                    ? source with { Embers = source.Embers - 1, Life = Math.Min(1000, source.Life + CombatMath.Ceiling((1000 - source.Life) * 0.15m)) }
                    : source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 10) };
                break;
            case "万毒蚀骨":
                source = CombatTriggerRegistry.Apply(source, "next.damage.flat",
                    5 * target.PoisonLayers + 2 * (target.BattleAttackReduction + target.BattleDefenseReduction));
                break;
            case "腐骨":
            {
                var shieldReduction = Math.Min(80, CombatMath.Floor(target.Shield * 0.20m));
                target = target with { Shield = Math.Max(0, target.Shield - shieldReduction) };
                break;
            }
            case "蚀骨之触":
            {
                var defenseReduction = CombatMath.Floor(2m + 0.5m * target.PoisonLayers);
                var shieldReduction = Math.Min(60, CombatMath.Floor(target.Shield * target.PoisonLayers * 0.08m));
                target = target with
                {
                    Defense = Math.Max(0, target.Defense - defenseReduction),
                    BattleDefenseReduction = target.BattleDefenseReduction + defenseReduction,
                    Shield = Math.Max(0, target.Shield - shieldReduction)
                };
                break;
            }
            case "毒刺": source = CombatTriggerRegistry.Apply(source with { PoisonEnchantmentLayers = source.PoisonEnchantmentLayers + 1 }, "next.damage.flat", 8); break;
            case "毒瓶": source = CombatTriggerRegistry.Apply(source with { PoisonEnchantmentLayers = source.PoisonEnchantmentLayers + 1 }, "next.damage.flat", 24 + (source.PoisonLayers > 0 ? 8 : 0)); break;
            case "毒雾": source = CombatTriggerRegistry.Apply(source with { PoisonEnchantmentLayers = source.PoisonEnchantmentLayers + 1 }, "next.damage.flat", 12); break;
            case "腐蚀": source = CombatTriggerRegistry.Apply(source with { PoisonEnchantmentLayers = source.PoisonEnchantmentLayers + 1 }, "next.damage.flat", 14); break;
            case "剧毒": source = CombatTriggerRegistry.Apply(source, "next.damage.flat", 30); break;
            case "腐溃": source = CombatTriggerRegistry.Apply(source, "next.damage.flat", 10 + 4 * source.PoisonLayers); break;
            case "蚀创": source = CombatTriggerRegistry.Apply(source, "next.damage.flat", 20 + 6 * source.PoisonLayers); break;
            case "爆裂": source = CombatTriggerRegistry.Apply(source, "next.fire.gap", -7.5m - (source.PoisonLayers >= 3 ? 5 : 0)); break;
            case "拆盾弹": source = CombatTriggerRegistry.Apply(source, "next.shield.penetration", 25); break;
             case "破障法阵": source = CombatTriggerRegistry.Apply(CombatTriggerRegistry.Apply(source, "next.shield.penetration", 60), "next.defense.penetration", 25); break;
            case "圣盾": source = source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 200) }; break;
            case "护盾强化": source = source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 60) }; break;
            case "盾墙": source = source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 120) }; break;
            case "愈合": source = source with { Life = Math.Min(1000, source.Life + 30) }; break;
            case "生命祝福": source = source with { Life = Math.Min(1000, source.Life + 70) }; break;
            case "大地之盾":
                source = source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 150) };
                if (source.Shield >= 200) source = source with { Defense = source.Defense + 5 };
                break;
            case "不坏壁垒": source = source with { Shield = source.Shield + 190 }; break;
            case "山岳壁垒": source = source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 190), Defense = source.Defense + 6 }; break;
            case "岩壁":
                source = source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 30) };
                if (source.Shield >= 100) source = source with { Defense = source.Defense + 2 };
                break;
            case "磐石":
                source = source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, 130) };
                if (source.Shield >= 200) source = source with { Attack = source.Attack + 4 };
                break;
            case "战术": source = CombatTriggerRegistry.Apply(source, "next.energy", 1); break;
            case "利刃":
                if (source.Attack >= 64) source = source with { Attack = source.Attack + 2 };
                break;
            default: return Array.Empty<EffectMutation>();
        }
        source = EmberConsumption.Record(source, Math.Max(0, context.SourceResources.Embers - source.Embers));
        return new[] { new EffectMutation(CardId, timing, 0, source, target, Array.Empty<CombatEvent>()) };
    }

    private static CombatResourceState ClearNegative(CombatResourceState state, int poisonLayers)
    {
        var removed = Math.Max(0, state.PoisonLayers - poisonLayers);
        return state with
        {
        Attack = state.Attack + state.BattleAttackReduction + state.TemporaryAttackReduction,
        Defense = state.Defense + state.BattleDefenseReduction + state.TemporaryDefenseReduction,
        BattleAttackReduction = 0,
        BattleDefenseReduction = 0,
        TemporaryAttackReduction = 0,
        TemporaryDefenseReduction = 0,
        TemporaryPoisonLayers = 0,
        PoisonLayers = poisonLayers,
        NegativeSuppressedUntilActionValue = 0
        } with { Attack = state.Attack + state.BattleAttackReduction + state.TemporaryAttackReduction + (state.PoisonExplosionActive ? removed : 0) };
    }

    private static CombatResourceState Heal(CombatResourceState state, int amount)
    {
        var actual = Math.Min(1000 - state.Life, Math.Max(0, amount));
        return state with { Life = state.Life + actual, ActualHealingThisBattle = state.ActualHealingThisBattle + actual };
    }

    private static CombatResourceState ApplyImmediatePoisonDamage(CombatResourceState source, CombatResourceState target, decimal multiplier)
    {
        if (target.PoisonLayers <= 0 || source.PoisonEnchantmentLayers <= 0) return target;
        var ratio = source.PoisonSpecialized ? 0.02m : 0.01m;
        var raw = source.Attack * source.PoisonEnchantmentLayers * target.PoisonLayers * ratio * multiplier;
        return target with { Life = target.Life - CombatMath.PoisonDamage(raw, target.Defense) };
    }

    private static CombatResourceState ApplyPoisonBurst(CombatResourceState source, CombatResourceState target, decimal multiplier)
    {
        var next = ApplyImmediatePoisonDamage(source, target, multiplier);
        return next with { PoisonLayers = 0 };
    }
}

public sealed record EffectMutation(
    string ResolverId,
    EffectTiming Timing,
    int Priority,
    CombatResourceState SourceResources,
    CombatResourceState TargetResources,
    IReadOnlyList<CombatEvent> Events
);

public interface ICardEffectResolver
{
    string CardId { get; }
    IReadOnlyList<EffectMutation> Resolve(EffectContext context, EffectTiming timing);
}

/// <summary>
/// Deterministic resolver pipeline. Resolvers never mutate CombatState directly;
/// they return resource snapshots and events that the engine commits atomically.
/// </summary>
public sealed class EffectPipeline
{
    private readonly IReadOnlyDictionary<string, ICardEffectResolver> _resolvers;

    public EffectPipeline(IEnumerable<ICardEffectResolver> resolvers)
    {
        _resolvers = resolvers.ToDictionary(resolver => resolver.CardId, StringComparer.Ordinal);
    }

    public bool HasResolver(string cardId) => _resolvers.ContainsKey(cardId);

    public IReadOnlyList<EffectMutation> Resolve(EffectContext context, EffectTiming timing)
    {
        if (context.Card is null || !_resolvers.TryGetValue(context.Card.CardId, out var resolver))
            throw new NotSupportedException($"UnsupportedCardEffect: {context.Card?.CardId ?? "<none>"}");
        return resolver.Resolve(context, timing)
            .OrderBy(mutation => mutation.Timing)
            .ThenBy(mutation => mutation.Priority)
            .ThenBy(mutation => mutation.ResolverId, StringComparer.Ordinal)
            .ToArray();
    }
}

public sealed class BaseStatsOrDeckEffectResolver : ICardEffectResolver
{
    public BaseStatsOrDeckEffectResolver(string cardId) => CardId = cardId;
    public string CardId { get; }

    public IReadOnlyList<EffectMutation> Resolve(EffectContext context, EffectTiming timing) =>
        timing == EffectTiming.OnPlay
            ? new[] { new EffectMutation(CardId, timing, 0, context.SourceResources, context.TargetResources, Array.Empty<CombatEvent>()) }
            : Array.Empty<EffectMutation>();
}






