using Godot;
using Magicians.Application;
using Magicians.Core.Common;
namespace Magicians.Tests;
public partial class V11ClientIntegrationRunner : Node
{
 public override void _Ready()
 {
  try {
   var root=ProjectSettings.GlobalizePath("res://");
   using(var session=GameSession.CreateSlice1(root)) {
    if(session.Cards.Version!="1.1" || session.Cards.Count!=252) throw new InvalidDataException("Client must load 252 frozen v1.1 cards.");
    CardPresentationRegression.Run(session.Cards, root);
    CardExecutionAudit.Run(session.Cards, Path.Combine(root, "..", "runtime", "v11-card-execution-audit.json"));
    DamageFormulaRegression.Run();
   }
   AiPrivacyRegression.Run(root);
   FullTournamentRegression.Run(root);
   GD.Print("V11_CLIENT_INTEGRATION_OK");GetTree().Quit(0);
  } catch(Exception e){GD.PushError(e.ToString());GetTree().Quit(1);}
 }
}
