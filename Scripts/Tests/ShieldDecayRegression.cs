using Magicians.Core.Cards;
using Magicians.Core.Combat;
using Magicians.Core.Common;

namespace Magicians.Tests;

public static class ShieldDecayRegression
{
    public static void Run(EffectContext baseline, EffectPipeline pipeline, CardDatabase database)
    {
        CombatResourceState Play(string id, CombatResourceState state) => pipeline.Resolve(baseline with
        {
            Card = new CardInstance(new CardInstanceId("decay:" + id), id, baseline.Source),
            SourceResources = state
        }, EffectTiming.OnPlay).Single().SourceResources;
        var activated = Play("大地之握", baseline.SourceResources with { Shield = 100 });
        var ordinary = Play("护盾", activated);
        if (ordinary.Shield != 135 || ordinary.ShieldDecay.PendingDamage != 100)
            throw new InvalidDataException("大地之握 must record actual old-shield decay times four.");
        var boosted = Play("握盾", Play("握盾", ordinary));
        if (boosted.ShieldDecay.MainDamage != 300 || boosted.ShieldDecay.NextBonusPercent != 200)
            throw new InvalidDataException("握盾 bonuses must stack additively.");
        var exempt = Play("不坏壁垒", activated);
        var temporary = Play("临时壁垒", activated);
        var consumed = Play("山岳之躯", activated);
        if (exempt.Shield != 300 || exempt.ShieldDecay.PendingDamage != 0 ||
            temporary.ShieldDecay.PendingDamage != 0 || consumed.ShieldDecay.PendingDamage != 0)
            throw new InvalidDataException("No-decay gains, temporary shields and active shield consumption must not generate decay damage.");
        var rounded = new ShieldDecayState(Active: true).OnOrdinaryGain(3);
        if (rounded.PendingDamage != 0 || boosted.ShieldDecay.AfterFire().MainDamage != 0 ||
            boosted.ShieldDecay.AfterFire().NextBonusPercent != 0 || !boosted.ShieldDecay.AfterFire().Active)
            throw new InvalidDataException("Decay must use actual integer shield loss and consume only next-fire resources.");
        var burstSource = activated with { EarthBarrierActive = true, EarthSpecialized = true, EarthLayers = 10 };
        var burst = pipeline.Resolve(baseline with
        {
            Card = new CardInstance(new CardInstanceId("grasp-burst"), "万钧碎盾", baseline.Source),
            SourceResources = burstSource,
            TargetResources = baseline.TargetResources with { Shield = 1000, Defense = 0 }
        }, EffectTiming.OnPlay).Single();
        if (burst.Events.Single().LifeDamage != 31 || burst.Events.Single().ShieldDamage != 31 ||
            burst.SourceResources.ShieldDecay.PendingDamage != 100)
            throw new InvalidDataException("大地之握 must give shield bursts 50% penetration, while active consumption adds no decay.");

        var engine = new Slice1CombatEngine(database);
        var a = new PlayerId("decay-a");
        var b = new PlayerId("decay-b");
        var state = engine.Start(new CombatSetup(new BattleId("decay-fire"),
            new CombatantSetup(a, new[] { new CardInstance(new CardInstanceId("decay-a"), "护盾", a) }, 1),
            new CombatantSetup(b, new[] { new CardInstance(new CardInstanceId("decay-b"), "护盾", b) }, 2)));
        // Earth gain must record this loss before the same shot reads its damage.
        state = state with
        {
            A = state.A with { Shield = 100, EarthLayers = 2, NextFire = 50, PendingSubmissiles = 1, ShieldDecay = new(Active: true) },
            B = state.B with { NextFire = 150 }
        };
        var pending = engine.Submit(state, new CombatCommand(state.Battle, a, state.Revision, new CombatAction(CombatActionKind.EndWindow)));
        var result = engine.Submit(pending.State, new CombatCommand(state.Battle, b, state.Revision, new CombatAction(CombatActionKind.EndWindow)));
        var main = result.Events.Single(item => item.Kind == "MainMissile");
        if (!result.Accepted || main.Amount != 140 || result.State.A.ShieldDecay.PendingDamage != 0 || result.State.B.Life != 853 ||
            result.Events.Single(item => item.Kind == "Submissile").Amount != 7)
            throw new InvalidDataException($"Earth pre-fire decay must damage the same shot and clear after firing: amount={main.Amount}, life={result.State.B.Life}.");
        // Advance through the next draw window without playing any cards. The
        // second shot may use only the new 19 shield loss, never the prior 25.
        var secondPending = engine.Submit(result.State, new CombatCommand(result.State.Battle, a, result.State.Revision,
            new CombatAction(CombatActionKind.EndWindow)));
        var second = engine.Submit(secondPending.State, new CombatCommand(result.State.Battle, b, result.State.Revision,
            new CombatAction(CombatActionKind.EndWindow)));
        var secondShot = second.Events.Single(e => e.Kind == "MainMissile" && e.Player == a);
        if (!second.Accepted || secondShot.Amount != 116 || second.State.A.ShieldDecay.PendingDamage != 0)
            throw new InvalidDataException($"大地之握 must reset after each main shot: expected second-shot damage 116, got {secondShot.Amount}.");
        var idle = state with
        {
            A = state.A with { EarthLayers = 0, PendingSubmissiles = 0, ShieldDecay = new(Active: true, PendingDamage: 100) },
            B = state.B with { NextFire = 1000 }
        };
        var idlePending = engine.Submit(idle, new CombatCommand(idle.Battle, a, idle.Revision, new CombatAction(CombatActionKind.EndWindow)));
        var idleFirst = engine.Submit(idlePending.State, new CombatCommand(idle.Battle, b, idle.Revision, new CombatAction(CombatActionKind.EndWindow)));
        var idleNext = engine.Submit(idleFirst.State, new CombatCommand(idle.Battle, a, idleFirst.State.Revision, new CombatAction(CombatActionKind.EndWindow)));
        var idleSecond = engine.Submit(idleNext.State, new CombatCommand(idle.Battle, b, idleFirst.State.Revision, new CombatAction(CombatActionKind.EndWindow)));
        if (idleSecond.Events.Single(e => e.Kind == "MainMissile" && e.Player == a).Amount != 40)
            throw new InvalidDataException("No new ordinary shield decay means no new grasp damage on the following main shot.");
        var reversed = state with { A = state.B, B = state.A };
        var reversedPending = engine.Submit(reversed, new CombatCommand(reversed.Battle, b, reversed.Revision, new CombatAction(CombatActionKind.EndWindow)));
        var reversedResult = engine.Submit(reversedPending.State, new CombatCommand(reversed.Battle, a, reversed.Revision, new CombatAction(CombatActionKind.EndWindow)));
        if (!reversedResult.Accepted || reversedResult.State.A.Life != 853 || reversedResult.State.B.ShieldDecay.PendingDamage != 0)
            throw new InvalidDataException("Shield decay damage must behave identically in both participant slots.");
        var prepared = new SnapshotCombatResolutionPolicy().PrepareBeforeFire(state.A with
        { EarthLayers = 0, NextMainTemporaryShieldPercent = 50 }, true);
        if (prepared.Shield != 130 || prepared.TemporaryShield != 30 || prepared.ShieldDecay.PendingDamage != 0)
            throw new InvalidDataException("焰心屏障 must add temporary shield without ordinary-shield decay damage.");
        var rewind = Play("时光倒流", boosted);
        if (rewind.RewindSnapshot is not { ShieldDecayActive: true })
            throw new InvalidDataException("Death rewind must snapshot the permanent grasp activation separately from next-shot resources.");
        VerifyActivationCommands(database);
    }

    private static void VerifyActivationCommands(CardDatabase database)
    {
        var a = new PlayerId("grasp-command-a");
        var b = new PlayerId("grasp-command-b");
        var cards = new[] { "大地之握", "握盾", "护盾" }
            .Select(id => new CardInstance(new CardInstanceId("grasp-command:" + id), id, a)).ToArray();
        var engine = new Slice1CombatEngine(database);
        var state = engine.Start(new CombatSetup(new BattleId("grasp-command"),
            new CombatantSetup(a, cards, 10),
            new CombatantSetup(b, new[] { new CardInstance(new CardInstanceId("grasp-enemy"), "护盾", b) }, 20)));
        state = state with { A = state.A with { Energy = 10, Shield = 100 } };
        var enemyEnd = engine.Submit(state, new CombatCommand(state.Battle, b, state.Revision,
            new CombatAction(CombatActionKind.EndWindow)));
        state = enemyEnd.State;
        foreach (var card in cards)
        {
            var result = engine.Submit(state, new CombatCommand(state.Battle, a, state.Revision,
                new CombatAction(CombatActionKind.PlayCard, card.InstanceId)));
            if (!result.Accepted) throw new InvalidDataException("Grasp authority command rejected: " + card.CardId);
            state = result.State;
        }
        if (!state.A.ShieldDecay.Active || state.A.ShieldDecay.PendingDamage != 100 ||
            state.A.ShieldDecay.NextBonusPercent != 100 || state.A.Shield != 135)
            throw new InvalidDataException("Grasp activation, next-shot bonus and ordinary gain were not committed by real card commands.");
        var repeated = engine.Submit(state, new CombatCommand(state.Battle, a, state.Revision,
            new CombatAction(CombatActionKind.PlayCard, cards[1].InstanceId)));
        if (repeated.Accepted || repeated.State.A != state.A)
            throw new InvalidDataException("Repeated clicks must not spend energy or apply 握盾 twice.");
    }
}

