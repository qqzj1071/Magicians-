using Godot;
using Magicians.Application;
using Magicians.Core.Common;
using Magicians.Core.Match;

namespace Magicians.Tests;

// Explicit release QA entry point, never active during normal double-click play.
public partial class ReleaseSmokeRunner : Node
{
    private double _seconds;
    public override void _Process(double delta)
    {
        _seconds += delta;
        try
        {
            if (_seconds > 120) throw new TimeoutException("Release smoke test exceeded 120 seconds.");
            var session = GameSession.Current ?? throw new InvalidOperationException("New game failed.");
            var state = session.Coordinator.CurrentState;
            var human = new PlayerId("human");
            if (state.Phase == MatchPhase.Draft && !state.Players[human].Draft.IsCompleted)
                session.Coordinator.Submit(new FinishDraftCommand(state.Id, human, new(state.EventSequence + 1)));
            if (state.Phase == MatchPhase.Combat) session.DelegateHumanCombat();
            if (state.Phase == MatchPhase.Settlement)
            {
                if (state.Round >= 2)
                {
                    GD.Print($"RELEASE_SMOKE_OK rounds={state.Round} battles={session.BattleAnnouncements.Count} pythonWorkers={session.Ai.WorkerCount}");
                    GetTree().Quit();
                }
                else session.AdvanceRound();
            }
        }
        catch (Exception error) { GD.PrintErr("RELEASE_SMOKE_FAILED " + error); GetTree().Quit(1); }
    }
}

