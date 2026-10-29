using System.Reflection;
using Godot;
using Magicians.Core.Cards;
using Magicians.Core.Combat;
using Magicians.Core.Common;

namespace Magicians.Tests;

// Focused formula checks, not another tournament sample.
public partial class V11RouteBalanceRunner : Node
{
    public override void _Ready()
    {
        try { Run(); GD.Print("V11_ROUTE_BALANCE_OK"); GetTree().Quit(0); }
        catch (Exception e) { GD.PushError(e.ToString()); GetTree().Quit(1); }
    }

    private static void Require(bool value, string message)
    {
        if (!value) throw new InvalidDataException(message);
    }

    private static void Run()
    {
        var db=CardDatabase.LoadFromJson(ProjectSettings.GlobalizePath("res://releases/v1.1/cards.json"));
        var a=new PlayerId("a"); var b=new PlayerId("b");
        var engine=new Slice1CombatEngine(db);
        var state=engine.Start(new CombatSetup(new BattleId("v11-formulas"),
            new CombatantSetup(a,new[] {new CardInstance(new CardInstanceId("a:1"),"防御强化",a)},1),
            new CombatantSetup(b,new[] {new CardInstance(new CardInstanceId("b:1"),"防御强化",b)},2))) with {ActionValue=100};
        var hit=typeof(Slice1CombatEngine).GetMethod("Hit",BindingFlags.NonPublic|BindingFlags.Static)!;
        (CombatantState Source,CombatantState Target) Hit(CombatantState source,CombatantState target,List<CombatEvent> events) =>
            ((CombatantState,CombatantState))hit.Invoke(null,new object[]{source,target,state,events})!;
        Require(CombatMath.MissileDamage(200,100,8,15)==121,"Arrow ignore must multiply the remaining defense.");
        var bloodlineSource=CombatResourceState.From(state.A with {Attack=100});
        var bloodline=new BasicImmediateEffectResolver("燃烧血统").Resolve(
            new EffectContext(state.Battle,100,a,b,null,bloodlineSource,CombatResourceState.From(state.B)),EffectTiming.OnPlay).Single().SourceResources;
        Require(bloodline.Attack==100 && bloodline.BurningBloodlineActive,"Bloodline must change the main-shot multiplier rather than permanently multiply the attack panel.");
        Require(new ShieldDecayState(Active:true).OnOrdinaryGain(100).MainDamage==75,"Grasp must record 25 lost shield at 300%.");
        var bloodEvents=new List<CombatEvent>();
        Hit(state.A with {Attack=100,BurningBloodlineActive=true,PendingSubmissiles=1},state.B with {Defense=0},bloodEvents);
        Require(bloodEvents.Any(e=>e.Kind=="MainMissile" && e.Amount==180) && bloodEvents.Any(e=>e.Kind=="Submissile" && e.Amount==35),"Bloodline 1.8 multiplier must affect only the main missile.");
        bloodEvents.Clear();
        Hit(state.A with {Attack=100,BurningBloodlineActive=true,EmberDamageActive=true,FireLayers=4,Embers=2,FireSpecialized=true},state.B with {Defense=0},bloodEvents);
        Require(bloodEvents.Any(e=>e.Kind=="MainMissile" && e.Amount==223),"Specialized bloodline must use 3% per fire layer per ember.");
        foreach(var used in new[]{false,true})
        foreach(var activated in new[]{false,true})
        foreach(var cycle in new[]{false,true})
        {
            var ash=engine.Start(new CombatSetup(new BattleId("ash-repeat"),
                new CombatantSetup(a,new[]{new CardInstance(new CardInstanceId("ash"),"灰烬重生",a)},1),
                new CombatantSetup(b,new[]{new CardInstance(new CardInstanceId("other"),"防御强化",b)},2)));
            ash=ash with {A=ash.A with {FireSpecialized=true,EmberDamageActive=activated,AshCycleActive=cycle,AshRebirthUsed=used,Embers=0,Energy=10}};
            var pending=engine.Submit(ash,new CombatCommand(ash.Battle,a,ash.Revision,new CombatAction(CombatActionKind.PlayCard,ash.A.CurrentPool.Single().InstanceId)));
            var resolved=engine.Submit(pending.State,new CombatCommand(ash.Battle,b,ash.Revision,new CombatAction(CombatActionKind.EndWindow)));
            Require(resolved.Accepted && resolved.State.A.Embers==(activated ? (cycle ? 3 : 1) : 0),"Ash rebirth requires the specialization card to be played, then grants one ember on every play.");
        }
        var events=new List<CombatEvent>();
        Hit(state.A with {Attack=200,WindLayers=2,WindSpecialized=true,WindGaleActive=true,WindArrowActive=true},
            state.B with {Defense=100,Shield=1000},events);
        Require(events.Any(e=>e.Kind=="MainMissile" && e.Amount==118 && e.ShieldDamage==127),"Arrow shield bonus must be 15%.");
        events.Clear();
        Hit(state.A with {Attack=100,WindChaseActive=true,LastMainMissileActionValue=50,LastMainMissileActualDamage=200},
            state.B with {Defense=0},events);
        Require(events.Any(e=>e.Kind=="MainMissile" && e.Amount==100),"Blade follow damage must expire at 50 action values.");
        events.Clear();
        Hit(state.A with {Attack=60,Defense=0},state.B with {Defense=0,Shield=100,EarthLayers=10,EarthSpecialized=true,EarthBarrierActive=true,BastionHeartActive=true},events);
        Require(events.Any(e=>e.Kind=="EarthReflect" && e.Amount==13),"Bastion must reflect absorbed 51 * 10 * 2.5% rounded up.");
        events.Clear();
        var water=Hit(state.A with {Life=500,Attack=100,WaterLayers=5,WaterSpecialized=true,TideActive=true,TideRefundPercent=25},
            state.B with {Defense=0},events).Source;
        Require(water.Life==520 && water.Tides==8m,"Echo must record actual healing * water layers * 8%.");
        events.Clear();
        var echo=Hit(state.A with {Life=500,Attack=100,WaterLayers=5,WaterSpecialized=true,TideActive=true,TideRefundPercent=25,NextTideHealingRecordBonusPercent=50},
            state.B with {Defense=0},events).Source;
        Require(echo.Tides==12m && echo.NextTideHealingRecordBonusPercent==0,"Echo must increase this shot healing record by 50% and consume the bonus.");
        events.Clear();
        var rock=Hit(state.A with {Attack=200,Defense=100},state.B with {Defense=0,Shield=100,EarthLayers=20,EarthSpecialized=true,EarthBarrierActive=true,ShieldBreakReturnPercent=40},events);
        Require(events.Any(e=>e.Kind=="EarthReflect" && e.Amount==40) && events.Any(e=>e.Kind=="ShieldBreakReturn" && e.Amount==40),"Rock must subtract 50% defense and return 40% of broken shield.");
        var effectContext=new EffectContext(state.Battle,100,a,b,null,CombatResourceState.From(state.A with {WaterLayers=3,WindLayers=3,TideActive=true}),CombatResourceState.From(state.B));
        var spring=new BasicImmediateEffectResolver("生命之泉").Resolve(effectContext,EffectTiming.OnPlay).Single().SourceResources;
        Require(spring.LifeSpringActive && spring.AttackIntervalModifier==0,"Spring must reduce interval by 4 + 0.5 * water layers.");
        var wind=new BasicImmediateEffectResolver("天岚").Resolve(effectContext,EffectTiming.OnPlay).Single().SourceResources;
        Require(wind.WindGaleActive && wind.AttackIntervalModifier==0,"Wind specialization must reduce interval by 4 + wind layers.");
        var echoCard=new BasicImmediateEffectResolver("回响之潮").Resolve(effectContext,EffectTiming.OnPlay).Single().SourceResources;
        Require(echoCard.NextTideDamageMultiplierPercent==140 && echoCard.NextTideHealingRecordBonusPercent==50,"Echo support must add 40% tide damage and 50% heal recording.");
        var creditState=EmberConsumption.Record(EmberConsumption.Record(state.A with {AshCycleActive=true,EmberDamageActive=true},1),5);
        Require(creditState.AshCyclePendingCredit==3,"Ash credit must cap at three across all consumption before a draw.");
        var draw=typeof(Slice1CombatEngine).GetMethod("Draw",BindingFlags.NonPublic|BindingFlags.Static)!;
        creditState=creditState with {DrawPile=Enumerable.Range(0,20).Select(i=>new CardInstance(new CardInstanceId("credit:"+i),"防御强化",a)).ToArray(),NextDrawBonus=1,NextEnergyBonus=1};
        var drawn=(CombatantState)draw.Invoke(null,new object[]{creditState})!;
        Require(drawn.CurrentPool.Count==9 && drawn.Energy==7 && drawn.AshCyclePendingCredit==0,"Ash must grant three cards/energy without consuming other bonuses, then reset.");
        var nextDraw=(CombatantState)draw.Invoke(null,new object[]{drawn})!;
        Require(nextDraw.CurrentPool.Count==5 && nextDraw.Energy==3,"Unused ash credit must not carry into later draws.");
        var burstContext=new EffectContext(state.Battle,100,a,b,null,CombatResourceState.From(state.A with {EarthLayers=10,EarthBarrierActive=true,EarthSpecialized=true,ShieldDecay=new ShieldDecayState(Active:true)}),CombatResourceState.From(state.B with {Shield=1000,Defense=40}));
        var burst=new ActiveShieldBurstResolver("岩核爆破").Resolve(burstContext,EffectTiming.OnPlay).Single();
        Require(burst.TargetResources.Life==1000 && burst.TargetResources.Shield==996,"Base shield burst must use 3% per earth layer and never bypass shields through Grasp.");
        var ashLink=typeof(Slice1CombatEngine).GetMethod("ApplyAshStartupLink",BindingFlags.NonPublic|BindingFlags.Static)!;
        var routeCard=new CardInstance(new CardInstanceId("route-link"),"灰烬循环",a);
        var specCard=new CardInstance(new CardInstanceId("spec-link"),"炽焰王冠",a);
        var filler=new CardInstance(new CardInstanceId("filler-link"),"防御强化",a);
        var linked=(CombatantState)ashLink.Invoke(null,new object[]{state.A with {Embers=0,EmberDamageActive=false,ExhaustedCards=new[]{routeCard},CurrentPool=Array.Empty<CardInstance>(),DrawPile=new[]{filler,specCard},DrawnThisWindow=new[]{"灰烬循环"}},"灰烬循环"})!;
        Require(linked.Embers==0 && linked.DrawPile[0].CardId=="炽焰王冠","Route-first must topdeck specialization without granting embers.");
        linked=(CombatantState)ashLink.Invoke(null,new object[]{linked with {EmberDamageActive=true,ExhaustedCards=new[]{routeCard,specCard},DrawPile=new[]{filler}},"炽焰王冠"})!;
        Require(linked.Embers==0 && linked.DrawPile.Count==1,"Specialization must not grant startup embers or retrieve an exhausted route.");
        var specFirst=(CombatantState)ashLink.Invoke(null,new object[]{state.A with {Embers=0,EmberDamageActive=true,ExhaustedCards=new[]{specCard},CurrentPool=Array.Empty<CardInstance>(),DrawPile=new[]{filler,routeCard}},"炽焰王冠"})!;
        Require(specFirst.Embers==0 && specFirst.DrawPile[0].CardId=="灰烬循环","Specialization-first topdecks the owned route without granting startup embers.");
        var alreadyDrawn=(CombatantState)ashLink.Invoke(null,new object[]{state.A with {Embers=0,EmberDamageActive=false,ExhaustedCards=new[]{routeCard},CurrentPool=Array.Empty<CardInstance>(),DrawPile=new[]{filler,specCard},DrawnThisWindow=new[]{"炽焰王冠","灰烬循环"}},"灰烬循环"})!;
        Require(alreadyDrawn.DrawPile[0].CardId=="防御强化","A counterpart drawn this window must not be moved again.");
        events.Clear();
        Hit(state.A with {Attack=100,WindChaseActive=true,LastMainMissileActionValue=75,LastMainMissileActualDamage=200},state.B with {Defense=0},events);
        Require(events.Any(e=>e.Kind=="MainMissile" && e.Amount==120),"Blade follow-up must be 200 * (1-25/50) * 20% = 20.");
        foreach (var layers in new[] { 1, 5, 16 })
        foreach (var shield in new[] { 0, 10000 })
        {
            events.Clear();
            var poisonHit = Hit(state.A with { Attack=100, PoisonEnchantmentLayers=layers },
                state.B with { Defense=0, Shield=shield, PoisonLayers=3 }, events);
            var expected = shield == 0 ? 1 : 0;
            Require(poisonHit.Target.PoisonLayers == 3 + expected, "Poison enchantment count must not multiply applied target stacks.");
            Require(events.Where(e=>e.Kind=="PoisonApplied").Sum(e=>e.Amount)==expected, "Poison log must report actual applied stacks.");
        }
        events.Clear();
        var extraPoison = Hit(state.A with { Attack=100, PoisonEnchantmentLayers=16, NextPoisonOnHitCharges=2, NextPoisonOnHitLayers=1 },
            state.B with { Defense=0 }, events);
        Require(extraPoison.Target.PoisonLayers==2 && extraPoison.Source.NextPoisonOnHitCharges==1,
            "Explicit next-hit poison bonus must add once and consume one charge.");
        foreach (var enemyFirst in new[] { false, true })
        {
            var rewindCard = new CardInstance(new CardInstanceId("rewind"), "时光倒流", a);
            var killCard = new CardInstance(new CardInstanceId("kill"), "万毒爆", b);
            var test = engine.Start(new CombatSetup(new BattleId("rewind-pair"),
                new CombatantSetup(a,new[]{rewindCard},1),new CombatantSetup(b,new[]{killCard},2)));
            test = test with { A=test.A with {Life=100,Energy=10,PoisonLayers=100},
                B=test.B with {Attack=100,Energy=10,PoisonEnchantmentLayers=16,PoisonSpecialized=true} };
            var first=enemyFirst?b:a;var second=enemyFirst?a:b;
            var one=engine.Submit(test,new CombatCommand(test.Battle,first,test.Revision,
                new CombatAction(CombatActionKind.PlayCard,enemyFirst?killCard.InstanceId:rewindCard.InstanceId)));
            var two=engine.Submit(one.State,new CombatCommand(test.Battle,second,test.Revision,
                new CombatAction(CombatActionKind.PlayCard,enemyFirst?rewindCard.InstanceId:killCard.InstanceId)));
            Require(two.Accepted && two.State.A.Life>0 && two.Events.Any(e=>e.Kind=="TimeRewind"),
                "Rewind must survive same-pair lethal in either submission order.");
        }
        var saved = new BasicImmediateEffectResolver("时光倒流").Resolve(new EffectContext(state.Battle,100,a,b,null,
            CombatResourceState.From(state.A),CombatResourceState.From(state.B)),EffectTiming.OnPlay).Single().SourceResources.RewindSnapshot;
        var rewindMethod=typeof(Slice1CombatEngine).GetMethod("TryRewind",BindingFlags.Static|BindingFlags.NonPublic)!;
        foreach(var time in new[]{100,299,300,301}) {
            var rewound=(CombatantState)rewindMethod.Invoke(null,new object[]{state.A with {Life=-5,RewindSnapshot=saved},time,new List<CombatEvent>(),0L})!;
            Require((rewound.Life>0)==(time<=300),"Rewind deadline must include all damage at exactly +200.");
        }
        GD.Print("TIME_REWIND_OK paired-lethal=both-orders deadline=inclusive");
        var finish=typeof(Slice1CombatEngine).GetMethod("FinishFire",BindingFlags.NonPublic|BindingFlags.Instance)!;
        var normal=(CombatantState)finish.Invoke(engine,new object[]{state.A,100})!;
        Require(normal.NextFire==150,"v1.1 base interval must be 50.");
        var growingWind=(CombatantState)finish.Invoke(engine,new object[]{state.A with {WindGaleActive=true,WindLayers=10},100})!;
        Require(growingWind.NextFire==136,"Wind interval must use current layers, not activation-time layers.");
        var springFire=(CombatantState)finish.Invoke(engine,new object[]{state.A with {LifeSpringActive=true,WaterLayers=3},100})!;
        Require(springFire.NextFire==144,"Water interval must use current layers and floor half units.");
        var poison=typeof(Slice1CombatEngine).GetMethod("ResolvePoisonForTarget",BindingFlags.NonPublic|BindingFlags.Static)!;
        var changed=((CombatantState Source,CombatantState Target))poison.Invoke(null,new object[]{
            state.A with {PlagueActive=true,PoisonEnchantmentLayers=5,PoisonDecayKeepLast=true},
            state.B with {Attack=100,Defense=100,PoisonLayers=4},100,0L,new List<CombatEvent>()})!;
        Require(changed.Target.Attack==86 && changed.Target.Defense==90,"Bone plague must use 0.6 / 0.4.");
        var decay=((CombatantState Source,CombatantState Target))poison.Invoke(null,new object[]{
            state.A with {Attack=100,PoisonExplosionActive=true,PoisonEnchantmentLayers=5},
            state.B with {Defense=0,PoisonLayers=4,NextPoisonDecayActionValue=50},100,0L,new List<CombatEvent>()})!;
        Require(decay.Source.Attack==101,"Poison layer decay must retain the already approved +1 attack growth.");
        foreach(var entry in new[]{("万毒爆",2m),("毒潮",2.5m),("毒爆弹",1.5m)})
        {
            var source=CombatResourceState.From(state.A with {Attack=100,PoisonSpecialized=true,PoisonEnchantmentLayers=5});
            var target=CombatResourceState.From(state.B with {Defense=0,PoisonLayers=4});
            var context=new EffectContext(state.Battle,100,a,b,null,source,target);
            var result=new BasicImmediateEffectResolver(entry.Item1).Resolve(context,EffectTiming.OnPlay).Single();
            Require(result.TargetResources.Life==1000-(int)(40m*entry.Item2) && result.TargetResources.PoisonLayers==0,
                entry.Item1+" must use the requested multiplier and consume poison.");
        }
    }
}
