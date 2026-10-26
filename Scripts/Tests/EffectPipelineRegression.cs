using Magicians.Core.Cards;
using Magicians.Core.Combat;
using Magicians.Core.Common;

namespace Magicians.Tests;

public static class EffectPipelineRegression
{
    public static void Run(CardDatabase database)
    {
        var registry = CardEffectRegistry.CreateSlice1(database);
        var pipeline = EffectPipelineDefaults.Create(database, registry);
        var source = new PlayerId("source");
        var target = new PlayerId("target");
        var card = new CardInstance(new CardInstanceId("pipeline:card"), "护盾", source);
        var resources = new CombatResourceState(
            Life: 1000, Shield: 0, Attack: 60, Defense: 20, Energy: 3, DeckElementCount: 3, PrimaryElement: "fire", ElementForgeActive: false, ElementForgeBonusLayers: 0, ElementForgePotentialLayers: 2, AttackIntervalModifier: 0,
            PermanentIntervalMultiplierPercent: 100, TemporaryIntervalMultiplierPercent: 100,
            NextIncomingDamageMultiplierPercent: 100, NextIncomingDamageFlat: 0,
            HealingReductionPercent: 0, HealingReductionUntilActionValue: 0,
            BattleIncomingDamageMultiplierPercent: 100, BattleIncomingDamageUntilActionValue: 0,
            TemporaryShield: 0, Tides: 0m, TideActive: false,
            NextTideDamageMultiplierPercent: 100, TideRefundPercent: 0, BloodTideActive: false,
            NextWaterShieldHealingMultiplierPercent: 100,
            ActualHealingThisBattle: 0m,
            CardsPlayedThisWindow: 0, GuardianBarrierActive: false, WarGodEmblemActive: false,
            RewindSnapshot: null,
            NextPoisonOnHitLayers: 0, NextPoisonOnHitCharges: 0, ExtraPoisonTickCharges: 0, PlagueLifeDamageActive: false,
            PoisonExplosionActive: false, PlagueActive: false, PlagueAttackReduction: 0, PlagueDefenseReduction: 0,
            WindLayers: 0, WaterLayers: 0, EarthLayers: 0, EarthBarrierActive: false, ShieldBreakReturnPercent: 0, ShieldBreakReturnFlat: 0, ShieldBreakDefenseMarkerActive: false, ShieldBreakDrawMarkerActive: false, ShieldBrokenThisBattle: false, FireLayers: 0, Embers: 0, EmberDamageActive: false, EmberCoreActive: false, AshRebirthUsed: false, AshCycleActive: false, ShuffleCount: 0, TemperBonusUses: 0, PoisonLayers: 0,
            NextDrawBonus: 0, NextEnergyBonus: 0, NextGapAdjustment: 0, PendingSubmissiles: 0,
            PendingWindSubmissiles: 0, NextMissileBonusPercent: 0, NextMissileBonusFlat: 0, NextMissileHealingPercent: 0,
            NextWindSubmissileFlat: 0, NextWindSubmissileAttackPercent: 0, WindTraceActive: false, WindTraceLayers: 0, WindTraceBonusLayers: 0,
            WindChaseActive: false, LastMainMissileActionValue: -1, LastMainMissileActualDamage: 0,
            MainDamageBonusUntilDrawPercent: 0,
            WindGaleActive: false, WindMainShotCount: 0, WindTraceExplosionMultiplierPercent: 0,
            WindArrowActive: false, NextShieldDamageMultiplierPercent: 0,
            NextShieldPenetrationPercent: 0, MainShieldPenetrationUntilDrawPercent: 0, MainDefensePenetrationPercent: 0, NextDefensePenetrationPercent: 0, NextMainTemporaryShieldPercent: 0,
            BattleAttackReduction: 0, BattleDefenseReduction: 0, NegativeSuppressedUntilActionValue: 0,
            TemporaryAttackReduction: 0, TemporaryDefenseReduction: 0, TemporaryPoisonLayers: 0,
            PoisonEnchantmentLayers: 0, NextPoisonDecayActionValue: 0,
            PoisonDecayIntervalPercent: 0, PoisonDecayProtectionCharges: 0, PoisonDecayKeepLast: false, PoisonSpecialized: false,
            FireSpecialized: false, WaterSpecialized: false, EarthSpecialized: false, WindSpecialized: false,
            Counters: new Dictionary<string, int>(), Statuses: new HashSet<string>());
        var context = new EffectContext(new BattleId("pipeline"), 0, source, target, card, resources, resources);
        ActiveShieldBurstRegression.Run(context, pipeline, database);
        ShieldDecayRegression.Run(context, pipeline, database);
        var ledgerCard = new CardInstance(new CardInstanceId("pipeline:ledger"), "灰烬账本", source);
        CombatResourceState Ledger(CombatResourceState input) => pipeline.Resolve(
            context with { Card = ledgerCard, SourceResources = input }, EffectTiming.OnPlay).Single().SourceResources;
        var unusedLedger = Ledger(resources with { UnredeemedEmbersSpent = 2 });
        if (unusedLedger.NextDrawBonus != 2 || unusedLedger.Embers != 0 || unusedLedger.UnredeemedEmbersSpent != 2)
            throw new InvalidDataException("灰烬账本不足三层时须保留进度并提供下抽奖励。");
        var redeemedLedger = Ledger(resources with { UnredeemedEmbersSpent = 7 });
        if (redeemedLedger.Embers != 1 || redeemedLedger.UnredeemedEmbersSpent != 4 || redeemedLedger.NextDrawBonus != 0)
            throw new InvalidDataException("灰烬账本每次打出只能兑换一次，不能同时获得下抽奖励。");
        var redeemedAgain = Ledger(redeemedLedger);
        if (redeemedAgain.Embers != 2 || redeemedAgain.UnredeemedEmbersSpent != 1)
            throw new InvalidDataException("灰烬账本重复兑换必须准确扣除未兑换进度。");
        var spendForLedger = pipeline.Resolve(context with
        {
            Card = new CardInstance(new CardInstanceId("pipeline:ledger-spend"), "焚心", source),
            SourceResources = resources with { Embers = 2, UnredeemedEmbersSpent = 1 }
        }, EffectTiming.OnPlay).Single().SourceResources;
        if (spendForLedger.UnredeemedEmbersSpent != 3 || Ledger(spendForLedger).Embers != 1)
            throw new InvalidDataException("主动消耗余烬必须计入灰烬账本进度。");
        var mutations = pipeline.Resolve(context, EffectTiming.OnPlay);
        if (mutations.Count != 1 || mutations[0].ResolverId != "护盾")
            throw new InvalidDataException("The effect pipeline did not resolve a registered card deterministically.");

        var ordered = new[] { EffectTiming.AfterDamage, EffectTiming.BeforeFire, EffectTiming.OnPlay }
            .OrderBy(timing => timing).ToArray();
        if (!ordered.SequenceEqual(new[] { EffectTiming.OnPlay, EffectTiming.BeforeFire, EffectTiming.AfterDamage }))
            throw new InvalidDataException("Global effect timing order is not stable.");

        var negative = resources with
        {
            Attack = 58,
            Defense = 16,
            BattleAttackReduction = 2,
            BattleDefenseReduction = 4,
            TemporaryAttackReduction = 2,
            TemporaryDefenseReduction = 2,
            PoisonLayers = 3,
            TemporaryPoisonLayers = 1
        };
        var cleanseContext = context with
        {
            Card = new CardInstance(new CardInstanceId("pipeline:cleanse"), "风之躯", source),
            SourceResources = negative
        };
        var cleansed = pipeline.Resolve(cleanseContext, EffectTiming.OnPlay).Single().SourceResources;
        if (cleansed.Attack != 62 || cleansed.Defense != 22 || cleansed.PoisonLayers != 0 ||
            cleansed.BattleAttackReduction != 0 || cleansed.BattleDefenseReduction != 0)
            throw new InvalidDataException("风之躯 did not clear permanent and temporary negative states from zero layers.");

        var immuneContext = context with
        {
            Card = new CardInstance(new CardInstanceId("pipeline:immune"), "威吓", source),
            ActionValue = 0,
            TargetResources = resources with { NegativeSuppressedUntilActionValue = 100 }
        };
        var immuneTarget = pipeline.Resolve(immuneContext, EffectTiming.OnPlay).Single().TargetResources;
        if (immuneTarget.Attack != resources.Attack)
            throw new InvalidDataException("Temporary negative immunity did not block a new negative effect.");

        var poisonControl = context with
        {
            Card = new CardInstance(new CardInstanceId("pipeline:poison-control"), "延毒", source),
            SourceResources = resources with { PoisonDecayIntervalPercent = 0, PoisonDecayProtectionCharges = 0 }
        };
        var extended = pipeline.Resolve(poisonControl, EffectTiming.OnPlay).Single().SourceResources;
        if (extended.PoisonDecayIntervalPercent != 15)
            throw new InvalidDataException("延毒 did not extend the poison decay interval.");
        poisonControl = poisonControl with { Card = new CardInstance(new CardInstanceId("pipeline:poison-lock"), "固毒", source), SourceResources = extended };
        var protectedPoison = pipeline.Resolve(poisonControl, EffectTiming.OnPlay).Single().SourceResources;
        if (protectedPoison.PoisonDecayProtectionCharges != 1)
            throw new InvalidDataException("固毒 did not add a poison decay protection charge.");

        var cycle = context with { Card = new CardInstance(new CardInstanceId("pipeline:cycle"), "循环", source) };
        var cycled = pipeline.Resolve(cycle, EffectTiming.OnPlay).Single().SourceResources;
        if (cycled.NextDrawBonus != 1 || cycled.NextEnergyBonus != 1)
            throw new InvalidDataException("循环 did not grant the next draw and energy bonuses.");

        var targetDebuff = context with
        {
            Card = new CardInstance(new CardInstanceId("pipeline:corrode-shield"), "腐骨", source),
            TargetResources = resources with { Shield = 100 }
        };
        var corroded = pipeline.Resolve(targetDebuff, EffectTiming.OnPlay).Single().TargetResources;
        if (corroded.Shield != 80)
            throw new InvalidDataException("腐骨 did not reduce the target shield by 20%.");

        targetDebuff = targetDebuff with
        {
            Card = new CardInstance(new CardInstanceId("pipeline:bone-touch"), "蚀骨之触", source),
            TargetResources = resources with { Shield = 100, PoisonLayers = 3, Defense = 20 }
        };
        var touched = pipeline.Resolve(targetDebuff, EffectTiming.OnPlay).Single().TargetResources;
        if (touched.Defense != 17 || touched.BattleDefenseReduction != 3 || touched.Shield != 76)
            throw new InvalidDataException("蚀骨之触 did not apply poison-scaled defense and shield reduction.");

        var bone = context with
        {
            Card = new CardInstance(new CardInstanceId("pipeline:bone"), "蚀骨", source),
            SourceResources = resources
        };
        var boneState = pipeline.Resolve(bone, EffectTiming.OnPlay).Single().SourceResources;
        if (boneState.PoisonDecayIntervalPercent != 100 || !boneState.PoisonDecayKeepLast)
            throw new InvalidDataException("蚀骨 did not retain the last poison layer and double its decay interval.");

        var devastating = context with
        {
            Card = new CardInstance(new CardInstanceId("pipeline:devastating-bone"), "万毒蚀骨", source),
            SourceResources = resources,
            TargetResources = resources with { PoisonLayers = 3, BattleAttackReduction = 2, BattleDefenseReduction = 4 }
        };
        var bonus = pipeline.Resolve(devastating, EffectTiming.OnPlay).Single().SourceResources;
        if (bonus.NextMissileBonusFlat != 27)
            throw new InvalidDataException("万毒蚀骨 did not calculate poison-scaled next missile damage.");

        var emberContext = context with
        {
            Card = new CardInstance(new CardInstanceId("pipeline:ember-heart"), "焚心", source),
            SourceResources = resources with { Life = 800, Embers = 2 }
        };
        var emberState = pipeline.Resolve(emberContext, EffectTiming.OnPlay).Single().SourceResources;
        if (emberState.Embers != 0 || emberState.Life != 860)
            throw new InvalidDataException("焚心 did not consume embers and restore 15% lost life per layer.");

        emberContext = emberContext with
        {
            Card = new CardInstance(new CardInstanceId("pipeline:ember-guard"), "余烬护心", source),
            SourceResources = resources with { Life = 800, Embers = 0 }
        };
        emberState = pipeline.Resolve(emberContext, EffectTiming.OnPlay).Single().SourceResources;
        if (emberState.Shield != 10 || emberState.Embers != 0)
            throw new InvalidDataException("余烬护心 did not grant fallback shield without embers.");

        var crown = context with
        {
            Card = new CardInstance(new CardInstanceId("pipeline:crown"), "炽焰王冠", source),
            SourceResources = resources
        };
        var crowned = pipeline.Resolve(crown, EffectTiming.OnPlay).Single().SourceResources;
        if (!crowned.EmberDamageActive)
            throw new InvalidDataException("炽焰王冠 did not activate ember damage.");

        var bloodline = context with
        {
            Card = new CardInstance(new CardInstanceId("pipeline:bloodline"), "燃烧血统", source),
            SourceResources = resources with { Attack = 60, AttackIntervalModifier = 0 }
        };
        var bloodlineState = pipeline.Resolve(bloodline, EffectTiming.OnPlay).Single().SourceResources;
        if (bloodlineState.Attack != 90 || bloodlineState.AttackIntervalModifier != 100)
            throw new InvalidDataException("燃烧血统 did not apply its attack and interval modifiers.");

        var rockWall = context with
        {
            Card = new CardInstance(new CardInstanceId("pipeline:rock-wall"), "裂岩护壁", source),
            SourceResources = resources with { Shield = 30 }
        };
        var rockWallState = pipeline.Resolve(rockWall, EffectTiming.OnPlay).Single().SourceResources;
        if (rockWallState.Shield != 103 || rockWallState.Defense != 24)
            throw new InvalidDataException("裂岩护壁 did not apply its shield threshold defense bonus.");

        var bonePoison = context with
        {
            Card = new CardInstance(new CardInstanceId("pipeline:bone-poison"), "渗骨毒素", source),
            SourceResources = resources
        };
        var bonePoisonState = pipeline.Resolve(bonePoison, EffectTiming.OnPlay).Single().SourceResources;
        if (bonePoisonState.MainShieldPenetrationUntilDrawPercent != 20)
            throw new InvalidDataException("渗骨毒素 did not arm temporary main projectile shield penetration.");

        var fountain = context with
        {
            Card = new CardInstance(new CardInstanceId("pipeline:fountain"), "生命之泉", source),
            SourceResources = resources with { WaterLayers = 5 }
        };
        var fountainState = pipeline.Resolve(fountain, EffectTiming.OnPlay).Single().SourceResources;
        if (fountainState.AttackIntervalModifier != -12 || fountainState.MainDefensePenetrationPercent != 20)
            throw new InvalidDataException("生命之泉 did not apply water-scaled interval and defense penetration.");

        var ashCycle = context with
        {
            Card = new CardInstance(new CardInstanceId("pipeline:ash-cycle"), "灰烬循环", source),
            SourceResources = resources
        };
        var ashCycleState = pipeline.Resolve(ashCycle, EffectTiming.OnPlay).Single().SourceResources;
        if (!ashCycleState.AshCycleActive)
            throw new InvalidDataException("灰烬循环 did not activate its shuffle and ember conversion state.");

        var heartBarrier = context with
        {
            Card = new CardInstance(new CardInstanceId("pipeline:heart-barrier"), "焰心屏障", source),
            SourceResources = resources
        };
        var heartBarrierState = pipeline.Resolve(heartBarrier, EffectTiming.OnPlay).Single().SourceResources;
        if (heartBarrierState.NextMainTemporaryShieldPercent != 50)
            throw new InvalidDataException("焰心屏障 did not arm its next-fire temporary shield lifecycle.");

        var emberCore = context with
        {
            Card = new CardInstance(new CardInstanceId("pipeline:ember-core"), "余烬之核", source),
            SourceResources = resources
        };
        var emberCoreState = pipeline.Resolve(emberCore, EffectTiming.OnPlay).Single().SourceResources;
        var scorch = context with
        {
            Card = new CardInstance(new CardInstanceId("pipeline:scorch"), "灼痛", source),
            SourceResources = resources
        };
        var scorchState = pipeline.Resolve(scorch, EffectTiming.OnPlay).Single().SourceResources;
        if (scorchState.NextMissileHealingPercent != 5)
            throw new InvalidDataException("灼痛 did not arm its conditional missile healing.");

        if (!emberCoreState.EmberCoreActive)
            throw new InvalidDataException("余烬之核 did not activate its permanent route state.");

        var emberTick = context with
        {
            Card = new CardInstance(new CardInstanceId("pipeline:ember-tick"), "余烬刻度", source),
            SourceResources = resources with { FireLayers = 6 }
        };
        var ticked = pipeline.Resolve(emberTick, EffectTiming.OnPlay).Single().SourceResources;
        if (ticked.Embers != 1 || ticked.NextDrawBonus != 0)
            throw new InvalidDataException("余烬刻度 did not grant an ember at six fire layers.");

        var wall = context with
        {
            Card = new CardInstance(new CardInstanceId("pipeline:earth-wall"), "山岳壁垒", source),
            SourceResources = resources
        };
        var walled = pipeline.Resolve(wall, EffectTiming.OnPlay).Single().SourceResources;
        if (walled.Shield != 190 || walled.Defense != 26)
            throw new InvalidDataException("山岳壁垒 did not grant its shield and defense.");

        if (!CombatTriggerRegistry.IsRegistered("next.damage.percent") ||
            !CombatTriggerRegistry.IsRegistered("next.fire.gap") ||
            CombatTriggerRegistry.All.Count < 12)
            throw new InvalidDataException("Temporary combat trigger registry is missing canonical one-shot entries.");
        var temporary = CombatTriggerRegistry.Apply(resources, "next.damage.percent", 18);
        temporary = CombatTriggerRegistry.Apply(temporary, "next.fire.gap", -20);
        temporary = CombatTriggerRegistry.Consume(temporary, TemporaryTrigger.NextFire);
        if (temporary.NextMissileBonusPercent != 0 || temporary.NextGapAdjustment != 0)
            throw new InvalidDataException("Temporary combat trigger consumption did not clear next-fire resources.");
        if (!CombatTriggerRegistry.OrderedTriggers.SequenceEqual(new[]
                { TemporaryTrigger.NextDraw, TemporaryTrigger.NextFire, TemporaryTrigger.WindowClosed, TemporaryTrigger.BattleFinished }))
            throw new InvalidDataException("Temporary trigger priority order is not stable.");

        var windContext = context with
        {
            Card = new CardInstance(new CardInstanceId("pipeline:wind-submissile"), "穿云", source),
            SourceResources = resources
        };
        var wind = pipeline.Resolve(windContext, EffectTiming.OnPlay).Single().SourceResources;
        if (wind.PendingWindSubmissiles != 1 || wind.NextWindSubmissileFlat != 25 || wind.NextWindSubmissileAttackPercent != 30 ||
            wind.NextMissileBonusPercent != 0)
            throw new InvalidDataException("Wind subprojectile parameters were not isolated from main-missile bonuses.");

        var galeContext = context with
        {
            Card = new CardInstance(new CardInstanceId("pipeline:gale"), "天岚", source),
            SourceResources = resources
        };
        var gale = pipeline.Resolve(galeContext, EffectTiming.OnPlay).Single().SourceResources;
        if (!gale.WindGaleActive || gale.WindMainShotCount != 0)
            throw new InvalidDataException("天岚 did not activate the main-shot counter.");

        var intervalContext = context with
        {
            Card = new CardInstance(new CardInstanceId("pipeline:interval"), "疾风连斩", source),
            SourceResources = resources
        };
        var interval = pipeline.Resolve(intervalContext, EffectTiming.OnPlay).Single().SourceResources;
        if (interval.AttackIntervalModifier != -3)
            throw new InvalidDataException("攻击间隔永久修正未通过统一资源注册表应用。");
        if (!LegendaryAbilityStatusRegistry.Contains("蚀命") ||
            LegendaryAbilityStatusRegistry.Get("风痕").StatusId != "legendary.wind.trace")
            throw new InvalidDataException("传奇能力永久状态注册表缺少稳定状态 ID。");
        var multiplied = CombatTriggerRegistry.Apply(interval, "battle.interval.multiplier", 80);
        multiplied = CombatTriggerRegistry.Apply(multiplied, "next.interval.multiplier", 50);
        if (multiplied.PermanentIntervalMultiplierPercent != 80 || multiplied.TemporaryIntervalMultiplierPercent != 50)
            throw new InvalidDataException("攻击间隔永久/临时乘算修正未正确叠加。");
        var vulnerability = CombatTriggerRegistry.Apply(resources, "battle.incoming.damage.multiplier", 23);
        vulnerability = CombatTriggerRegistry.Apply(vulnerability, "battle.incoming.damage.multiplier", 30);
        if (vulnerability.BattleIncomingDamageMultiplierPercent != 153)
            throw new InvalidDataException("多层易伤没有按百分比加算叠加。");

        var unsupported = new CardInstance(new CardInstanceId("pipeline:unsupported"), "missing-effect-id", source);
        var unsupportedContext = context with { Card = unsupported };
        try
        {
            pipeline.Resolve(unsupportedContext, EffectTiming.OnPlay);
            throw new InvalidDataException("An unregistered effect was resolved instead of being blocked.");
        }
        catch (NotSupportedException exception) when (exception.Message.StartsWith("UnsupportedCardEffect", StringComparison.Ordinal))
        {
            // Expected until the target-debuff resolver is implemented.
        }
    }
}


















