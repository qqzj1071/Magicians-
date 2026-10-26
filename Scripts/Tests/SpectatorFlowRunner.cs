using Godot;
using Magicians.Application;
using Magicians.Core.Common;
using Magicians.Core.Combat;
using Magicians.Core.Match;
using Magicians.Presentation;

namespace Magicians.Tests;

public partial class SpectatorFlowRunner : Node
{
    private GameSession _session = null!;
    private MatchViewController _match = null!;
    private double _elapsed;
    public override void _Ready()
    {
        try
        {
            var root = ProjectSettings.GlobalizePath("res://");
            var scenario = Slice1Scenario.Load(Path.Combine(root, "Data/slice1/scenario.json")) with
            { InitialTournamentLife = 1, InitialStudyPoints = 2 };
            _session = GameSession.CreateScenario(root, scenario, 20261026);
            GameSession.Current = _session; _session.BeginDraft();
            _match = GD.Load<PackedScene>("res://Scenes/Match/Match.tscn").Instantiate<MatchViewController>();
            AddChild(_match);
        }
        catch (Exception error) { GD.PrintErr("SPECTATOR_SETUP_FAILED " + error); GetTree().Quit(1); }
    }

    public override void _Process(double delta)
    {
        try
        {
            _elapsed += delta;
            if (_elapsed > 120) throw new TimeoutException("Spectator flow did not reach a champion.");
            var state = _session.Coordinator.CurrentState;
            var human = new PlayerId("human");
            if (state.Phase == MatchPhase.Draft && !state.Players[human].Draft.IsCompleted)
                _session.Coordinator.Submit(new FinishDraftCommand(state.Id, human, new(state.EventSequence + 1)));
            if (!_match.IsWatchingAi && state.Players[human].TournamentLife <= 0)
                _match.WatchAiToChampion();
            if (state.Phase == MatchPhase.Combat && !_match.IsWatchingAi)
            {
                var manager = _session.EnsureBattleInstances();
                foreach (var battle in manager.Instances.Values.ToArray())
                {
                    var current = battle.State;
                    if (current.Phase == CombatPhase.Finished) continue;
                    foreach (var actor in new[] { current.A.Player, current.B.Player })
                    {
                        current = manager.Instances[battle.Pairing.BattleId].State;
                        if (current.Phase == CombatPhase.Finished || current.EndedWindows.Contains(actor) || current.PendingActions.Any(p => p.Player == actor)) continue;
                        if (actor == human)
                            _session.SubmitCombat(new CombatCommand(current.Battle, human, current.Revision, new CombatAction(CombatActionKind.EndWindow)));
                    }
                }
            }
            if (_match.IsWatchingAi && state.Phase == MatchPhase.Finished)
            {
                var champions = TournamentStandings.Champions(state);
                if (champions.Count == 0) throw new InvalidDataException("Spectator mode finished without champion.");
                GD.Print($"SPECTATOR_FLOW_OK champions={string.Join(',', champions)} rounds={state.Round}");
                _match.QueueFree(); _session.Dispose(); GameSession.Current = null; GetTree().Quit();
            }
        }
        catch (Exception error) { GD.PrintErr("SPECTATOR_FLOW_FAILED " + error); GetTree().Quit(1); }
    }
}
