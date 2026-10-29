using Magicians.Core.Cards;
using Magicians.Core.Combat;
using Magicians.Core.Common;

namespace Magicians.Tests;

public static class BastionHeartRegression
{
    public static void Run(CardDatabase database)
    {
        var engine = new Slice1CombatEngine(database);
        var a = new PlayerId("bastion-a");
        var b = new PlayerId("bastion-b");
        CombatState Setup() => engine.Start(new CombatSetup(new BattleId("bastion"),
            new CombatantSetup(a, new[] { new CardInstance(new CardInstanceId("bastion-card"), "壁垒之心", a) }, 1),
            new CombatantSetup(b, new[] { new CardInstance(new CardInstanceId("bastion-enemy"), "护盾", b) }, 2)));
        CombatResolution EndBoth(CombatState state)
        {
            var pending = engine.Submit(state, new CombatCommand(state.Battle, a, state.Revision, new CombatAction(CombatActionKind.EndWindow)));
            return engine.Submit(pending.State, new CombatCommand(state.Battle, b, state.Revision, new CombatAction(CombatActionKind.EndWindow)));
        }
        var baseState = Setup();
        var played = engine.Submit(baseState, new CombatCommand(baseState.Battle, a, baseState.Revision,
            new CombatAction(CombatActionKind.PlayCard, baseState.A.CurrentPool.Single().InstanceId, SearchTargets: Array.Empty<CardInstanceId>())));
        var resolved = engine.Submit(played.State, new CombatCommand(baseState.Battle, b, baseState.Revision, new CombatAction(CombatActionKind.EndWindow)));
        if (!resolved.Accepted || !resolved.State.A.BastionHeartActive || resolved.State.A.NextEnergyBonus != 1 ||
            resolved.State.A.ExhaustedCards.Count != 1)
            throw new InvalidDataException("壁垒之心 must activate, grant next-draw energy, and leave the battle deck.");

        var reflected = EndBoth(baseState with
        {
            A = baseState.A with { NextFire = 150, Shield = 100, Defense = 0, EarthLayers = 10,
                EarthBarrierActive = true, EarthSpecialized = true, BastionHeartActive = true },
            B = baseState.B with { NextFire = 50, Attack = 60, Defense = 0 }
        });
        if (reflected.State.A.Shield != 49 || !reflected.Events.Any(e => e.Kind == "EarthReflect" && e.Amount == 13))
            throw new InvalidDataException("壁垒之心 must reduce normal damage by 15% and reflect absorbed damage even without shield break.");
        var additive = EndBoth(baseState with
        {
            A = baseState.A with { NextFire = 150, Shield = 100, Defense = 0, BastionHeartActive = true, NextIncomingDamageMultiplierPercent = 70 },
            B = baseState.B with { NextFire = 50, Attack = 60, Defense = 0 }
        });
        if (additive.State.A.Shield != 67)
            throw new InvalidDataException("Bastion and next-hit reduction must add to 45% total reduction.");
        var execute = EndBoth(baseState with
        {
            A = baseState.A with { Shield = 100, Defense = 20, EarthLayers = 10,
                EarthBarrierActive = true, EarthSpecialized = true, BastionHeartActive = true },
            B = baseState.B with { Life = 30, Defense = 0, Shield = 0 }
        });
        if (execute.State.Phase != CombatPhase.Finished || execute.State.A.Defense != 20 ||
            !execute.Events.Any(e => e.Kind == "AutomaticShieldExecute" && e.Amount == 35))
            throw new InvalidDataException("Bastion automatic shield execute must retain the shield-quantity formula without resetting defense.");
    }
}
