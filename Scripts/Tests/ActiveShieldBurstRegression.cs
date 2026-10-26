using Magicians.Core.Cards;
using Magicians.Core.Combat;
using Magicians.Core.Common;

namespace Magicians.Tests;

public static class ActiveShieldBurstRegression
{
    public static void Run(EffectContext baseline, EffectPipeline pipeline, CardDatabase database)
    {
        foreach (var cardId in new[] { "岩核爆破", "万钧碎盾" })
        {
            var heavy = cardId == "万钧碎盾";
            var gain = heavy ? 100 : 80;
            EffectMutation Resolve(CombatResourceState source, CombatResourceState target) => pipeline.Resolve(
                baseline with { Card = new CardInstance(new CardInstanceId("burst:" + cardId), cardId, baseline.Source),
                    SourceResources = source, TargetResources = target }, EffectTiming.OnPlay).Single();
            var source = baseline.SourceResources with { Shield = 100, EarthLayers = 10, EarthBarrierActive = false };
            var target = baseline.TargetResources with { Life = 1000, Shield = 10, Defense = 0 };
            var inactive = Resolve(source, target);
            if (inactive.SourceResources.Shield != 75 + gain || inactive.TargetResources != target)
                throw new InvalidDataException(cardId + ": inactive specialization must only grant ordinary shield.");

            source = source with { EarthBarrierActive = true, TemporaryShield = 20 };
            var result = Resolve(source, target);
            var consumed = 75 + gain;
            var expectedDamage = CombatMath.Ceiling(consumed * 10 * 0.035m);
            var expectedRefund = heavy ? CombatMath.Ceiling(consumed * 0.30m) : 30;
            if (result.SourceResources.Shield != expectedRefund || result.SourceResources.TemporaryShield != 0 ||
                result.SourceResources.ShieldBrokenThisBattle || result.TargetResources.Shield != 0 ||
                result.TargetResources.Life != 1000 - expectedDamage + 10 || result.Events.Single().Amount != expectedDamage)
                throw new InvalidDataException(cardId + ": consumption, shield absorption or survival refund failed.");
            var lethal = Resolve(source, target with { Shield = 0, Life = expectedDamage });
            if (lethal.SourceResources.Shield != 0 || lethal.TargetResources.Life != 0)
                throw new InvalidDataException(cardId + ": lethal burst must not refund shield.");
            var blocked = Resolve(source, target with { Defense = 10000 });
            if (blocked.Events.Single().Amount != 0 || blocked.SourceResources.Shield != expectedRefund)
                throw new InvalidDataException(cardId + ": fully defended burst must allow zero damage and refund.");
            var upgraded = Resolve(source with { EarthSpecialized = true, ShieldBreakReturnPercent = 40 }, target with { Defense = 20 });
            if (upgraded.Events.Single().Amount != CombatMath.Ceiling(consumed * 10 * 0.025m - 4))
                throw new InvalidDataException(cardId + ": upgraded reflect formula failed.");
            var unrelated = Resolve(source with { NextMissileBonusPercent = 300, WindLayers = 100, Embers = 10 }, target);
            if (unrelated.TargetResources != result.TargetResources)
                throw new InvalidDataException(cardId + ": projectile modifiers leaked into shield burst.");

            // Exercise the real command path as well as the resolver, including card stats,
            // first enchantment layer, energy cost and authority event revision.
            var enemy = new PlayerId("burst-enemy");
            var card = new CardInstance(new CardInstanceId("play:" + cardId), cardId, baseline.Source);
            var engine = new Slice1CombatEngine(database);
            var state = engine.Start(new CombatSetup(new BattleId("play:" + cardId),
                new CombatantSetup(baseline.Source, new[] { card }, 11),
                new CombatantSetup(enemy, new[] { new CardInstance(new CardInstanceId("enemy:" + cardId), "护盾", enemy) }, 12)));
            state = state with { A = state.A with { Shield = 100, EarthLayers = 9, EarthBarrierActive = true },
                B = state.B with { Shield = 10, Defense = 0 } };
            var pending = engine.Submit(state, new CombatCommand(state.Battle, state.A.Player, state.Revision,
                new CombatAction(CombatActionKind.PlayCard, card.InstanceId)));
            var resolved = engine.Submit(pending.State, new CombatCommand(state.Battle, enemy, state.Revision,
                new CombatAction(CombatActionKind.EndWindow)));
            if (!resolved.Accepted || resolved.State.A.Shield != expectedRefund ||
                resolved.State.B.Life != result.TargetResources.Life ||
                resolved.State.A.Energy != 3 - database.Get(cardId).Cost ||
                resolved.Events.Single(item => item.Kind == "ActiveShieldBurst").Revision != resolved.State.Revision)
                throw new InvalidDataException(cardId + ": authoritative card command path failed.");
        }
        VerifyLedgerCommands(database);
    }

    private static void VerifyLedgerCommands(CardDatabase database)
    {
        var a = new PlayerId("ledger-a");
        var b = new PlayerId("ledger-b");
        var engine = new Slice1CombatEngine(database);
        var state = engine.Start(new CombatSetup(new BattleId("ledger-commands"),
            new CombatantSetup(a, new[] { new CardInstance(new CardInstanceId("ledger-a"), "灰烬账本", a) }, 1),
            new CombatantSetup(b, new[] { new CardInstance(new CardInstanceId("ledger-b"), "灰烬账本", b) }, 2)));
        // Both sides fire at 50, before the draw boundary. Both must retain the
        // consumed-ember history even when outgoing attacks use a shared snapshot.
        state = state with
        {
            A = state.A with { NextFire = 50, Embers = 3, EmberDamageActive = true },
            B = state.B with { NextFire = 50, Embers = 3, EmberDamageActive = true }
        };
        var pending = engine.Submit(state, new CombatCommand(state.Battle, a, state.Revision,
            new CombatAction(CombatActionKind.EndWindow)));
        var fired = engine.Submit(pending.State, new CombatCommand(state.Battle, b, state.Revision,
            new CombatAction(CombatActionKind.EndWindow)));
        if (!fired.Accepted || fired.State.A.UnredeemedEmbersSpent != 3 || fired.State.B.UnredeemedEmbersSpent != 3)
            throw new InvalidDataException("Both firing sides must record actual ember consumption.");
        var play = engine.Submit(fired.State, new CombatCommand(state.Battle, a, fired.State.Revision,
            new CombatAction(CombatActionKind.PlayCard, fired.State.A.CurrentPool.Single().InstanceId)));
        var redeemed = engine.Submit(play.State, new CombatCommand(state.Battle, b, fired.State.Revision,
            new CombatAction(CombatActionKind.PlayCard, fired.State.B.CurrentPool.Single().InstanceId)));
        if (!redeemed.Accepted || redeemed.State.A.Embers != 1 || redeemed.State.B.Embers != 1 ||
            redeemed.State.A.UnredeemedEmbersSpent != 0 || redeemed.State.B.UnredeemedEmbersSpent != 0)
            throw new InvalidDataException("灰烬账本 command path failed to redeem both players' consumption history.");
    }
}
