using Godot;
using Magicians.Application;
using Magicians.Core.Common;
using Magicians.Core.Match;

namespace Magicians.Tests;

// Explicit release QA entry point, never active during normal double-click play.
public partial class ReleaseSmokeRunner : Node
{
    private double _seconds;
    private bool _checkedMetadata;
    public override void _Process(double delta)
    {
        _seconds += delta;
        try
        {
            if (_seconds > 120) throw new TimeoutException("Release smoke test exceeded 120 seconds.");
            var session = GameSession.Current ?? throw new InvalidOperationException("New game failed.");
            if (!_checkedMetadata)
            {
                if (session.Cards.Version != "1.1" || session.Cards.Count != 252)
                    throw new InvalidDataException("Release must load 252 v1.1 cards.");
                GD.Print($"RELEASE_METADATA cards={session.Cards.Version}/{session.Cards.Count} model={session.Ai.ModelHash} cardsHash={session.Ai.SourceHashes["releases/v1.1/cards.json"]}");
                _checkedMetadata = true;
            }
            var state = session.Coordinator.CurrentState;
            var human = new PlayerId("human");
            if (state.Phase == MatchPhase.Draft && !state.Players[human].Draft.IsCompleted)
                session.Coordinator.Submit(new FinishDraftCommand(state.Id, human, new(state.EventSequence + 1)));
            if (state.Phase == MatchPhase.Combat) session.DelegateHumanCombat();
            if (state.Phase == MatchPhase.Settlement)
            {
                if (state.Round >= 2)
                {
                    foreach (var id in new[] { "ai-1", "ai-2", "ai-3" })
                        if (!session.Ai.Traces.Any(t => t.Player == id && t.Stage == "draft") ||
                            !session.Ai.Traces.Any(t => t.Player == id && t.Stage == "combat"))
                            throw new InvalidDataException("Missing draft/combat AI inference: " + id);
                    GD.Print($"RELEASE_SMOKE_OK rounds={state.Round} battles={session.BattleAnnouncements.Count} pythonWorkers={session.Ai.WorkerCount}");
                    GetTree().Quit();
                }
                else session.AdvanceRound();
            }
        }
        catch (Exception error) { GD.PrintErr("RELEASE_SMOKE_FAILED " + error); GetTree().Quit(1); }
    }
}
