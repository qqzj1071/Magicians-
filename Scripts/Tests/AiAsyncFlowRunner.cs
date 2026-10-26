using System.Diagnostics;
using Godot;
using Magicians.Application;
using Magicians.Core.Combat;
using Magicians.Core.Common;

namespace Magicians.Tests;

public partial class AiAsyncFlowRunner : Node
{
    private GameSession _session = null!;
    private readonly Stopwatch _clock = Stopwatch.StartNew();
    private double _maxTickMilliseconds;
    public override void _Ready()
    {
        Engine.MaxFps = 120;
        _session = GameSession.CreateSlice1(ProjectSettings.GlobalizePath("res://"), 20261026);
        _session.BeginDraft();
    }

    public override void _Process(double delta)
    {
        try
        {
            if (_clock.Elapsed.TotalSeconds > 120) throw new TimeoutException("Asynchronous AI flow timed out.");
            var state = _session.Coordinator.CurrentState;
            var human = new PlayerId("human");
            if (state.Phase == MatchPhase.Draft && !state.Players[human].Draft.IsCompleted)
                _session.Coordinator.Submit(new FinishDraftCommand(state.Id, human, new(state.EventSequence + 1)));
            if (state.Phase == MatchPhase.Combat)
                foreach (var instance in _session.EnsureBattleInstances().Instances.Values.ToArray())
                {
                    if (instance.State.Phase != CombatPhase.Decision ||
                        (instance.State.A.Player != human && instance.State.B.Player != human) ||
                        instance.State.EndedWindows.Contains(human) || instance.State.PendingActions.Any(p => p.Player == human)) continue;
                    _session.SubmitCombat(new CombatCommand(instance.State.Battle, human, instance.State.Revision, new CombatAction(CombatActionKind.EndWindow)));
                }
            var tick = Stopwatch.StartNew();
            _session.TickAutonomous();
            _maxTickMilliseconds = Math.Max(_maxTickMilliseconds, tick.Elapsed.TotalMilliseconds);
            state = _session.Coordinator.CurrentState;
            if (state.Phase == MatchPhase.Settlement)
            {
                if (state.Round >= 2)
                {
                    if (_maxTickMilliseconds >= 500) throw new InvalidDataException("AI inference blocked an authority/UI tick.");
                    GD.Print($"AI_ASYNC_FLOW_OK rounds={state.Round} maxTickMs={_maxTickMilliseconds:F2}");
                    SetProcess(false);
                    GetTree().Quit();
                }
                else _session.AdvanceRound();
            }
        }
        catch (Exception error) { GD.PrintErr("AI_ASYNC_FLOW_FAILED " + error); GetTree().Quit(1); }
    }

    public override void _ExitTree() => _session?.Dispose();
}
