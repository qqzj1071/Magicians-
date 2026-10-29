using Godot;
using System.Reflection;
using Magicians.Application;
using Magicians.Core.Cards;
using Magicians.Core.Combat;
using Magicians.Core.Common;
namespace Magicians.Tests;
public partial class ResourceCarryRunner : Node {
 public override void _Ready() { try { Run(); GD.Print("RESOURCE_CARRY_OK");GetTree().Quit(); } catch(Exception e) { GD.PrintErr(e);GetTree().Quit(1); } }
 static void Check(bool v,string m) {if(!v)throw new Exception(m);}
 static void Run() {
 var db=CardDatabase.LoadFromJson(ProjectSettings.GlobalizePath("res://releases/v1.1/cards.json"));
 var draw=typeof(Slice1CombatEngine).GetMethod("Draw",BindingFlags.NonPublic|BindingFlags.Static)!;
 foreach(var entry in new[]{("战术大师",0,1),("战术",0,1),("鼓舞",0,1),("整理",2,-1),("速读",1,0),("翻阅",1,0),("通晓",2,0),("灵感涌现",2,1),("循环",1,1),("禁忌知识",3,1),("魔力契约",0,0)}) {
 var a=new PlayerId("a");var b=new PlayerId("b");var engine=new Slice1CombatEngine(db);
 var card=new CardInstance(new CardInstanceId("test"),entry.Item1,a);
 var state=engine.Start(new CombatSetup(new BattleId("test"),new CombatantSetup(a,new[]{card},1),new CombatantSetup(b,new[]{new CardInstance(new CardInstanceId("b"),"护盾",b)},2)));
 state=state with {A=state.A with {Energy=20}};
 var pending=engine.Submit(state,new CombatCommand(state.Battle,a,state.Revision,new CombatAction(CombatActionKind.PlayCard,card.InstanceId)));
 var result=engine.Submit(pending.State,new CombatCommand(state.Battle,b,state.Revision,new CombatAction(CombatActionKind.EndWindow)));
 Check(result.Accepted,entry.Item1+" rejected");var self=result.State.A;
 Check(self.NextDrawBonus==entry.Item2 && self.NextEnergyBonus==entry.Item3,entry.Item1+" pending rewards");
 var pile=Enumerable.Range(0,30).Select(i=>new CardInstance(new CardInstanceId("pile"+i),"护盾",a)).ToArray();
 self=self with {DrawPile=pile,DiscardPile=Array.Empty<CardInstance>()};
 var next=(CombatantState)draw.Invoke(null,new object[]{self})!;
 var contract=entry.Item1=="魔力契约";
 Check(next.Energy==3+entry.Item3+(contract?1:0) && next.CurrentPool.Count==5+entry.Item2-(contract?1:0),entry.Item1+" next draw grants");
 Check(next.NextEnergyBonus==0 && next.NextDrawBonus==0,entry.Item1+" consumed");
 var after=(CombatantState)draw.Invoke(null,new object[]{next})!;
 Check(after.Energy==(contract?4:3)&&after.CurrentPool.Count==(contract?4:5),entry.Item1+" following window");
 }
 var seen = new HashSet<string>();
 for (var seed = 0; seed < 32; seed++) {
  using var ai = new TrainedAiRuntime(ProjectSettings.GlobalizePath("res://"), seed);
  Check(ai.Styles.Count == 3 && ai.Styles.Values.Distinct().Count() == 3, "AI styles must be unique within a match");
  using var repeat = new TrainedAiRuntime(ProjectSettings.GlobalizePath("res://"), seed);
  Check(ai.Styles.All(p => repeat.Styles[p.Key] == p.Value), "Fixed seed must reproduce styles");
  foreach(var style in ai.Styles.Values) seen.Add(style);
 }
 Check(seen.Count == 6, "All six styles must be reachable");
 GD.Print("AI_STYLE_ASSIGNMENT_OK seeds=32 unique=3 reproducible=true styles=6");
 using var session=GameSession.CreateSlice1(ProjectSettings.GlobalizePath("res://"));session.BeginDraft();session.SaveLocalRecord();Check(session.LocalRecordError is null,"local JSON save failed");
 }
}
