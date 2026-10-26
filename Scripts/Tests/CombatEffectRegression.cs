using Magicians.Core.Cards;
using Magicians.Core.Combat;
using Magicians.Core.Common;

namespace Magicians.Tests;

public static class CombatEffectRegression
{
    private static readonly string[] ImplementedCards =
    {
        "包扎", "小治疗", "小盾", "水膜", "坚岩", "岩甲", "壁障", "整理", "速读", "鼓舞", "短促", "微风", "蓄能", "疾风", "威吓", "削弱", "破甲", "利刃", "攻守", "火星", "火苗", "毒甲", "毒涌"
    };

    public static void Run(CardDatabase database)
    {
        var engine = new Slice1CombatEngine(database);
        foreach (var cardId in ImplementedCards)
        {
            var owner = new PlayerId("a");
            var opponent = new PlayerId("b");
            var card = new CardInstance(new CardInstanceId($"a:{cardId}"), cardId, owner);
            var enemyCard = new CardInstance(new CardInstanceId($"b:{cardId}"), "攻击强化", opponent);
            var state = engine.Start(new CombatSetup(
                new BattleId($"effect:{cardId}"),
                new CombatantSetup(owner, new[] { card }, 101),
                new CombatantSetup(opponent, new[] { enemyCard }, 102)));
            if (cardId is "包扎" or "小治疗" or "水膜")
                state = state with { A = state.A with { Life = 900 } };
            if (cardId == "壁障")
                state = state with { A = state.A with { Shield = 30 } };
            if (cardId is "坚岩" or "岩甲")
                state = state with { A = state.A with { Shield = 100 } };
            if (cardId == "毒涌")
                state = state with { A = state.A with { PoisonLayers = 3 } };
            var play = engine.Submit(state, new CombatCommand(
                state.Battle, owner, state.Revision, new CombatAction(CombatActionKind.PlayCard, card.InstanceId)));
            var resolved = engine.Submit(play.State, new CombatCommand(
                state.Battle, opponent, state.Revision, new CombatAction(CombatActionKind.EndWindow)));
            if (!play.Accepted || !resolved.Accepted || resolved.State.A.DiscardPile.Count != 1)
                throw new InvalidDataException($"Effect regression could not resolve '{cardId}'.");

            if (cardId == "包扎" && resolved.State.A.Life != 925)
                throw new InvalidDataException("包扎 did not apply its healing effect.");
            if (cardId == "小治疗" && resolved.State.A.Life != 940)
                throw new InvalidDataException("小治疗 did not apply its healing effect.");
            if (cardId == "小盾" && resolved.State.A.Shield < 50)
                throw new InvalidDataException("小盾 did not apply its shield effect.");
            if (cardId == "水膜" && resolved.State.A.Life != 920)
                throw new InvalidDataException("水膜 did not apply its healing effect.");
            if (cardId == "毒甲" && resolved.State.A.Shield < 30)
                throw new InvalidDataException("毒甲 did not apply its shield effect.");
            if (cardId == "壁障" && resolved.State.A.Defense != 25)
                throw new InvalidDataException("壁障 did not apply its conditional defense effect.");
            if (cardId == "坚岩" && resolved.State.A.Defense != 22)
                throw new InvalidDataException("坚岩 did not apply its conditional defense effect.");
            if (cardId == "岩甲" && resolved.State.A.Attack != 63)
                throw new InvalidDataException("岩甲 did not apply its conditional attack effect.");
            if (cardId == "整理" && resolved.State.A.NextDrawBonus != 2)
                throw new InvalidDataException("整理 did not apply its draw bonus.");
            if (cardId == "速读" && resolved.State.A.NextDrawBonus != 1)
                throw new InvalidDataException("速读 did not apply its draw bonus.");
            if (cardId == "鼓舞" && resolved.State.A.NextEnergyBonus != 1)
                throw new InvalidDataException("鼓舞 did not apply its energy bonus.");
            if (cardId == "短促" && resolved.State.A.NextGapAdjustment != -15)
                throw new InvalidDataException("短促 did not apply its fire-gap adjustment.");
            if (cardId == "微风" && resolved.State.A.PendingSubmissiles != 1)
                throw new InvalidDataException("微风 did not apply its pending-submissile resource.");
            if (cardId == "蓄能" && resolved.State.A.NextMissileBonusPercent != 14)
                throw new InvalidDataException("蓄能 did not apply its missile bonus resource.");
            if (cardId == "疾风" && resolved.State.A.PendingWindSubmissiles != 1)
                throw new InvalidDataException("疾风 did not apply its wind-submissile resource.");
            if (cardId is "威吓" or "削弱" && resolved.State.B.Attack != 58)
                throw new InvalidDataException($"{cardId} did not apply its target attack reduction.");
            if (cardId == "破甲" && (resolved.State.B.Defense != 16 || resolved.State.B.BattleDefenseReduction != 4))
                throw new InvalidDataException("破甲 did not apply its target defense reduction.");
            if (cardId == "利刃" && resolved.State.A.Attack != 66)
                throw new InvalidDataException("利刃 did not apply its conditional attack effect.");
            if (cardId == "毒涌" && (resolved.State.A.PoisonLayers != 1 || resolved.State.A.NextDrawBonus != 2 || resolved.State.A.NextGapAdjustment != -15))
                throw new InvalidDataException("毒涌 did not consume poison and apply its temporary rewards.");
        }

        var enchantOrderState = engine.Start(new CombatSetup(
            new BattleId("enchantment-order"),
            new CombatantSetup(new PlayerId("a"), new[] { new CardInstance(new CardInstanceId("a:war-intent"), "战意", new PlayerId("a")) }, 801),
            new CombatantSetup(new PlayerId("b"), new[] { new CardInstance(new CardInstanceId("b:war-intent"), "护盾", new PlayerId("b")) }, 802)));
        enchantOrderState = enchantOrderState with { A = enchantOrderState.A with { FireLayers = 5 } };
        var enchantPending = engine.Submit(enchantOrderState, new CombatCommand(
            enchantOrderState.Battle, enchantOrderState.A.Player, enchantOrderState.Revision,
            new CombatAction(CombatActionKind.PlayCard, enchantOrderState.A.CurrentPool.Single().InstanceId)));
        var enchantPlay = engine.Submit(enchantPending.State, new CombatCommand(
            enchantOrderState.Battle, enchantOrderState.B.Player, enchantPending.State.Revision,
            new CombatAction(CombatActionKind.EndWindow)));
        if (!enchantPlay.Accepted || enchantPlay.State.A.FireLayers != 6 || enchantPlay.State.A.Attack != 73)
            throw new InvalidDataException($"Element enchantment ordering failed: accepted={enchantPlay.Accepted}, layers={enchantPlay.State.A.FireLayers}, attack={enchantPlay.State.A.Attack}, rejection={enchantPlay.Rejection?.Code}.");

        var lifecycleState = engine.Start(new CombatSetup(
            new BattleId("status-lifecycle"),
            new CombatantSetup(new PlayerId("a"), new[] { new CardInstance(new CardInstanceId("a:lifecycle"), "护盾", new PlayerId("a")) }, 201),
            new CombatantSetup(new PlayerId("b"), new[] { new CardInstance(new CardInstanceId("b:lifecycle"), "护盾", new PlayerId("b")) }, 202)));
        lifecycleState = lifecycleState with
        {
            A = lifecycleState.A with
            {
                TemporaryAttackReduction = 2,
                TemporaryDefenseReduction = 2,
                TemporaryPoisonLayers = 1,
                NegativeSuppressedUntilActionValue = 100
            }
        };
        var endA = engine.Submit(lifecycleState, new CombatCommand(lifecycleState.Battle, lifecycleState.A.Player, lifecycleState.Revision, new CombatAction(CombatActionKind.EndWindow)));
        var endB = engine.Submit(endA.State, new CombatCommand(lifecycleState.Battle, lifecycleState.B.Player, lifecycleState.Revision, new CombatAction(CombatActionKind.EndWindow)));
        if (!endB.Accepted || endB.State.ActionValue != 100 || endB.State.A.TemporaryAttackReduction != 0 ||
            endB.State.A.TemporaryDefenseReduction != 0 || endB.State.A.TemporaryPoisonLayers != 0 ||
            endB.State.A.NegativeSuppressedUntilActionValue != 0)
            throw new InvalidDataException("Temporary negative statuses did not expire at the 100-action draw boundary.");

        var poisonState = engine.Start(new CombatSetup(
            new BattleId("poison-lifecycle"),
            new CombatantSetup(new PlayerId("a"), new[] { new CardInstance(new CardInstanceId("a:poison"), "毒甲", new PlayerId("a")) }, 301),
            new CombatantSetup(new PlayerId("b"), new[] { new CardInstance(new CardInstanceId("b:poison"), "护盾", new PlayerId("b")) }, 302)));
        poisonState = poisonState with
        {
            ActionValue = 100,
            A = poisonState.A with { PoisonEnchantmentLayers = 1, NextFire = 1000 },
            B = poisonState.B with { PoisonLayers = 2, NextPoisonDecayActionValue = 100, NextFire = 1000 }
        };
        var poisonEndA = engine.Submit(poisonState, new CombatCommand(poisonState.Battle, poisonState.A.Player, poisonState.Revision, new CombatAction(CombatActionKind.EndWindow)));
        var poisonEndB = engine.Submit(poisonEndA.State, new CombatCommand(poisonState.Battle, poisonState.B.Player, poisonState.Revision, new CombatAction(CombatActionKind.EndWindow)));
        var poisonDamageIndex = poisonEndB.Events.ToList().FindIndex(item => item.Kind == "PoisonDamage");
        var poisonDecayIndex = poisonEndB.Events.ToList().FindIndex(item => item.Kind == "PoisonDecay");
        if (poisonDamageIndex < 0 || poisonDecayIndex < poisonDamageIndex || poisonEndB.State.B.PoisonLayers != 1)
            throw new InvalidDataException($"Poison damage/decay order failed: action={poisonEndB.State.ActionValue}, events={string.Join(',', poisonEndB.Events.Select(item => item.Kind))}, layers={poisonEndB.State.B.PoisonLayers}.");

        var earthState = engine.Start(new CombatSetup(
            new BattleId("earth-simultaneous-fire"),
            new CombatantSetup(new PlayerId("a"), new[] { new CardInstance(new CardInstanceId("a:earth"), "坚岩", new PlayerId("a")) }, 401),
            new CombatantSetup(new PlayerId("b"), new[] { new CardInstance(new CardInstanceId("b:earth"), "护盾", new PlayerId("b")) }, 402)));
        earthState = earthState with
        {
            ActionValue = 0,
            A = earthState.A with { EarthLayers = 1, NextFire = 0, Attack = 60, Defense = 20 },
            B = earthState.B with { NextFire = 0, Attack = 60, Defense = 20 }
        };
        var earthA = engine.Submit(earthState, new CombatCommand(earthState.Battle, earthState.A.Player, earthState.Revision, new CombatAction(CombatActionKind.EndWindow)));
        var earthB = engine.Submit(earthA.State, new CombatCommand(earthState.Battle, earthState.B.Player, earthState.Revision, new CombatAction(CombatActionKind.EndWindow)));
        if (!earthB.Events.Any(item => item.Player == earthState.B.Player && item.Kind == "MainMissile" && item.ShieldDamage >= 2))
            throw new InvalidDataException("Earth shield was not available before the simultaneous firing group.");

        var emberState = engine.Start(new CombatSetup(
            new BattleId("ember-full-damage"),
            new CombatantSetup(new PlayerId("a"), new[] { new CardInstance(new CardInstanceId("a:ember"), "护盾", new PlayerId("a")) }, 501),
            new CombatantSetup(new PlayerId("b"), new[] { new CardInstance(new CardInstanceId("b:ember"), "护盾", new PlayerId("b")) }, 502))) with
        {
            ActionValue = 0,
            A = engine.Start(new CombatSetup(
                new BattleId("ember-inner"),
                new CombatantSetup(new PlayerId("a"), new[] { new CardInstance(new CardInstanceId("a:ember-inner"), "护盾", new PlayerId("a")) }, 501),
                new CombatantSetup(new PlayerId("b"), new[] { new CardInstance(new CardInstanceId("b:ember-inner"), "护盾", new PlayerId("b")) }, 502))).A with
            {
                FireLayers = 2, Embers = 2, EmberDamageActive = true, NextFire = 0, Attack = 60
            },
            B = engine.Start(new CombatSetup(
                new BattleId("ember-inner-2"),
                new CombatantSetup(new PlayerId("a"), new[] { new CardInstance(new CardInstanceId("a:ember-inner-2"), "护盾", new PlayerId("a")) }, 501),
                new CombatantSetup(new PlayerId("b"), new[] { new CardInstance(new CardInstanceId("b:ember-inner-2"), "护盾", new PlayerId("b")) }, 502))).B with
            {
                Shield = 100, NextFire = 1000, Defense = 0
            }
        };
        var emberA = engine.Submit(emberState, new CombatCommand(emberState.Battle, emberState.A.Player, emberState.Revision, new CombatAction(CombatActionKind.EndWindow)));
        var emberB = engine.Submit(emberA.State, new CombatCommand(emberState.Battle, emberState.B.Player, emberState.Revision, new CombatAction(CombatActionKind.EndWindow)));
        var emberHit = emberB.Events.Single(item => item.Kind == "MainMissile" && item.Player == emberState.A.Player);
        if (emberHit.Amount != 66 || emberHit.ShieldDamage != 66 || emberB.State.A.Embers != 0 || !emberB.Events.Any(item => item.Kind == "EmberSpent"))
            throw new InvalidDataException($"Ember amplification did not apply to full main-missile damage: amount={emberHit.Amount}, shield={emberHit.ShieldDamage}.");

        var reflectState = engine.Start(new CombatSetup(
            new BattleId("earth-reflect"),
            new CombatantSetup(new PlayerId("a"), new[] { new CardInstance(new CardInstanceId("a:reflect"), "护盾", new PlayerId("a")) }, 601),
            new CombatantSetup(new PlayerId("b"), new[] { new CardInstance(new CardInstanceId("b:reflect"), "护盾", new PlayerId("b")) }, 602)));
        reflectState = reflectState with
        {
            ActionValue = 0,
            A = reflectState.A with { NextFire = 0, Attack = 60, Defense = 0 },
            B = reflectState.B with
            {
                NextFire = 1000, Shield = 50, Defense = 0, EarthLayers = 1,
                EarthBarrierActive = true, EarthSpecialized = true, ShieldBreakReturnPercent = 40
            }
        };
        var reflectA = engine.Submit(reflectState, new CombatCommand(reflectState.Battle, reflectState.A.Player, reflectState.Revision, new CombatAction(CombatActionKind.EndWindow)));
        var reflectB = engine.Submit(reflectA.State, new CombatCommand(reflectState.Battle, reflectState.B.Player, reflectState.Revision, new CombatAction(CombatActionKind.EndWindow)));
        if (!reflectB.Events.Any(item => item.Kind == "EarthReflect" && item.LifeDamage == 2) ||
            !reflectB.Events.Any(item => item.Kind == "ShieldBreakReturn" && item.Amount == 20) || reflectB.State.B.Shield != 20)
            throw new InvalidDataException("Earth shield-break reflection and return-shield resolution failed.");

        var registry = CardEffectRegistry.CreateSlice1(database);
        foreach (var cardId in registry.ImplementedCardIds.OrderBy(id => id, StringComparer.Ordinal))
        {
            var owner = new PlayerId("smoke-a");
            var opponent = new PlayerId("smoke-b");
            var card = new CardInstance(new CardInstanceId($"smoke:{cardId}"), cardId, owner);
            var smoke = engine.Start(new CombatSetup(
                new BattleId($"smoke:{cardId}"),
                new CombatantSetup(owner, new[] { card }, 701),
                new CombatantSetup(opponent, new[] { new CardInstance(new CardInstanceId($"smoke-target:{cardId}"), "护盾", opponent) }, 702)));
            var played = engine.Submit(smoke, new CombatCommand(smoke.Battle, owner, smoke.Revision,
                new CombatAction(CombatActionKind.PlayCard, card.InstanceId)));
            if (!played.Accepted)
                throw new InvalidDataException($"Implemented card failed client combat smoke test: {cardId}, rejection={played.Rejection?.Code}.");
            var executed = engine.Submit(played.State, new CombatCommand(smoke.Battle, opponent, smoke.Revision,
                new CombatAction(CombatActionKind.EndWindow)));
            if (!executed.Accepted || executed.State.A.Energy < 0 || executed.State.A.Shield < 0 ||
                executed.State.A.Attack != 60 + database.Get(cardId).Attack && database.Get(cardId).Text.StartsWith("无", StringComparison.Ordinal))
                throw new InvalidDataException("Full-card execution audit failed: " + cardId);
        }
    }
}

