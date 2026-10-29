using Godot;
using Magicians.Application;
using Magicians.Core.Cards;
using Magicians.Core.Combat;
using Magicians.Core.Common;
using Magicians.Presentation;
namespace Magicians.Tests;
public partial class SearchPanelRunner : Control {
 public override void _Ready() {
 try {
 using var session=GameSession.CreateSlice1(ProjectSettings.GlobalizePath("res://"));
 var player=new PlayerId("human");
 var candidates=new[]{"护盾","时光倒流","战术大师","整理","毒甲"}.Select((n,i)=>new CardInstance(new CardInstanceId("candidate"+i),n,player)).ToArray();
 foreach(var max in new[]{1,2}) {
 var popup=new SearchSelectionPanel();AddChild(popup);var calls=0;CardInstanceId[] chosen=Array.Empty<CardInstanceId>();
 popup.Open(session,new SearchSelectionSession(player,new CardInstanceId("search"),"大检索",candidates,max,max>1),ids=>{calls++;chosen=ids;});
 var grid=popup.GetNode<GridContainer>("Layout/Scroll/Cards");Check(grid.GetChildCount()==5,"Every revealed candidate needs a full card");
 Check(grid.GetChildren().All(n=>n.GetChildren().OfType<CardView>().Count()==1),"Full card views missing");
 popup.EmitSignal(Window.SignalName.CloseRequested);Check(!popup.IsQueuedForDeletion()&&calls==0,"Close must not cancel or commit");
 var rows=grid.GetChildren();((CheckButton)rows[2].GetNode("Select")).ButtonPressed=true;
 if(max==2)((CheckButton)rows[0].GetNode("Select")).ButtonPressed=true;
 var confirm=popup.GetNode<Button>("Layout/Confirm");Check(!confirm.Disabled,"Selection should enable confirmation");
 confirm.EmitSignal(Button.SignalName.Pressed);confirm.EmitSignal(Button.SignalName.Pressed);
 Check(calls==1 && chosen[0]==candidates[2].InstanceId && chosen.Length==max,"Selection order or exactly-once commit failed"); popup.Free();
 }
 GD.Print("SEARCH_PANEL_OK cards=5 no-cancel=true ordered=true commit-once=true");GetTree().Quit();
 } catch(Exception e){GD.PrintErr(e);GetTree().Quit(1);}
 }
 static void Check(bool v,string message){if(!v)throw new Exception(message);}
}
