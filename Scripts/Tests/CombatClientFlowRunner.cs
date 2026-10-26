using System.Diagnostics;
using System.Text.Json;
using Godot;
using Magicians.Application;
using Magicians.Core.AI;
using Magicians.Core.Combat;
using Magicians.Core.Common;
using Magicians.Presentation;

namespace Magicians.Tests;

/// <summary>Real inference integration: background progress, player privacy,
/// mid-window delegation, authority rejection and round-scoped reset.</summary>
public partial class CombatClientFlowRunner : Node
{
    private GameSession? _session;

    public override async void _Ready()
    {
        try
        {
            Engine.MaxFps = 120;
            var root = ProjectSettings.GlobalizePath("res://");
            CombatFeedbackRegression.Run(root);
            AiPrivacyRegression.Run(root);
            _session = GameSession.CreateSlice1(root, 20261026);
            GameSession.Current = _session;
            Require(!_session.DelegateHumanCombat(), "Delegation must be rejected before combat.");
            _session.BeginDraft();
            var matchView = GD.Load<PackedScene>("res://Scenes/Match/Match.tscn").Instantiate<MatchViewController>();
            AddChild(matchView);
            matchView.SetProcess(false);
            var board = matchView.GetNode<CombatBoardController>("Layout/Content/CombatBoard");
            var human = new PlayerId("human");
            var clock = Stopwatch.StartNew();
            var delegatedRound = 0;
            var checkedPrivacy = false;
            var backgroundAdvanced = false;
            var maxTick = 0d;
            while (clock.Elapsed.TotalSeconds < 120)
            {
                var match = _session.Coordinator.CurrentState;
                if (match.Phase == MatchPhase.Draft && !match.Players[human].Draft.IsCompleted)
                {
                    Require(!_session.IsHumanCombatDelegated, "Delegation leaked into the next draft.");
                    _session.Coordinator.Submit(new FinishDraftCommand(match.Id, human, new(match.EventSequence + 1)));
                }
                if (_session.Coordinator.CurrentState.Phase == MatchPhase.Combat)
                {
                    var manager = _session.EnsureBattleInstances();
                    var battle = _session.HumanBattle!;
                    var view = CombatPlayerView.Create(battle, human)!;
                    if (match.Round == 1 && view.ActionValue == 0)
                    {
                        var statusButtons = board.GetNode<HBoxContainer>("Panel/Column/StatusButtons");
                        Require(statusButtons.GetChildCount() == 2, "Status controls missing");
                    }
                    if (!checkedPrivacy)
                    {
                        VerifyVisibility(battle);
                        checkedPrivacy = true;
                    }
                    if (match.Round == 1 && delegatedRound == 0)
                    {
                        var background = manager.Instances.Values.Single(i => i.Pairing.BattleId != battle.Pairing.BattleId);
                        Require(view.ActionValue == 0 && view.CanAct, "Player must be able to act while the other match runs.");
                        Require(_session.Ai.Traces.All(t => t.Player != "human" || t.Stage != "combat"), "Manual player was automated before consent.");
                        backgroundAdvanced = background.State.Revision >= 2;
                    }
                    if (delegatedRound < match.Round && (match.Round > 1 || backgroundAdvanced))
                    {
                        // Submit a manual end-window before handing over, including
                        // the case where the opponent still has a pending decision.
                        var manual = _session.SubmitCombat(new CombatCommand(view.Battle, human, view.Revision,
                            new CombatAction(CombatActionKind.EndWindow)));
                        Require(manual.Accepted, "Manual input should work before round delegation.");
                        board.AppendEvents(manual.Events);
                        board.Refresh();
                        var button = board.GetNode<Button>("Panel/Column/DelegateCombat");
                        Require(button.Visible && !button.Disabled, "Round delegation button is unavailable.");
                        var before = JsonSerializer.Serialize(_session.HumanBattle!.State);
                        button.EmitSignal(Button.SignalName.Pressed);
                        Require(_session.IsHumanCombatDelegated && button.Disabled, "Button did not enable the round delegate.");
                        Require(before == JsonSerializer.Serialize(_session.HumanBattle.State), "Delegation changed an already committed combat action.");
                        var rejected = _session.SubmitCombat(new CombatCommand(view.Battle, human,
                            _session.HumanBattle.State.Revision, new CombatAction(CombatActionKind.EndWindow)));
                        Require(!rejected.Accepted && rejected.Rejection?.Code == "CombatDelegated" &&
                            before == JsonSerializer.Serialize(_session.HumanBattle.State), "Manual commands must be rejected atomically after delegation.");
                        delegatedRound = match.Round;
                    }
                }
                var tick = Stopwatch.StartNew();
                var events = _session.TickAutonomous();
                maxTick = Math.Max(maxTick, tick.Elapsed.TotalMilliseconds);
                if (_session.HumanBattle is { } current)
                    Require(events.All(e => e.Player == current.Pairing.PlayerA || e.Player == current.Pairing.PlayerB),
                        "Background battle leaked into player combat events.");
                if (delegatedRound == 0) Require(events.Count == 0, "Background AI battle polluted a paused player's log.");
                board.AppendEvents(events);
                board.Refresh();
                match = _session.Coordinator.CurrentState;
                if (match.Phase == MatchPhase.Settlement)
                {
                    matchView.Refresh();
                    var broadcast = matchView.GetNode<Label>("Layout/BattleBroadcast");
                    Require(_session.BattleAnnouncements.Count == match.Round * 2 && broadcast.Visible &&
                        _session.BattleAnnouncements.TakeLast(2).All(a => broadcast.Text.Contains(a.Text[(a.Text.IndexOf('·') + 1)..].Trim(), StringComparison.Ordinal)),
                        "A completed background or player battle was not broadcast.");
                    Require(!_session.DelegateHumanCombat(), "Finished combat accepted delegation.");
                    if (match.Round == 2)
                    {
                        var missileLog = board.GetNode<RichTextLabel>("Panel/Column/Logs/MissileColumn/MissileLog").Text;
                        Require(missileLog.Contains("主弹结算", StringComparison.Ordinal) && missileLog.Contains("生命损失", StringComparison.Ordinal),
                            "Actual battle missile settlements were not displayed.");
                        Require(backgroundAdvanced && delegatedRound == 2 && maxTick < 500,
                            "Background progress, round reset or nonblocking AI requirement failed.");
                        Require(_session.Ai.Traces.Any(t => t.Player == "human" && t.Stage == "combat" && t.Decision.Contains("play", StringComparison.Ordinal)),
                            "Delegate did not play a card using the trained planner.");
                        GD.Print($"COMBAT_CLIENT_FLOW_OK rounds=2 background-progress=OK privacy=OK mid-window-delegate=OK reset=OK maxTickMs={maxTick:F2}");
                        matchView.QueueFree();
                        await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
                        _session.Dispose();
                        GameSession.Current = null;
                        GetTree().Quit();
                        return;
                    }
                    _session.AdvanceRound();
                    Require(!_session.IsHumanCombatDelegated, "Next round did not restore manual control.");
                }
                await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            }
            throw new TimeoutException("Combat client integration exceeded 120 seconds.");
        }
        catch (Exception error)
        {
            GD.PrintErr("COMBAT_CLIENT_FLOW_FAILED " + error);
            GetTree().Quit(1);
        }
    }

    private static void VerifyVisibility(BattleInstance battle)
    {
        var human = new PlayerId("human");
        var original = CombatPlayerView.Create(battle, human)!;
        Require(original.Self.Attack == (battle.State.A.Player == human ? battle.State.A.Attack : battle.State.B.Attack) &&
            original.Opponent.Defense == (battle.State.A.Player == human ? battle.State.B.Defense : battle.State.A.Defense),
            "Displayed combat attributes differ from authoritative live attributes.");
        var enemy = original.Opponent.Player;
        var other = battle.State.A.Player == enemy ? battle.State.A : battle.State.B;
        var hidden = other with { CurrentPool = Array.Empty<Magicians.Core.Cards.CardInstance>(),
            DrawPile = other.DrawPile.Reverse().ToArray(), RandomState = 123 };
        var mutated = battle with { State = battle.State with
        {
            A = battle.State.A.Player == enemy ? hidden : battle.State.A,
            B = battle.State.B.Player == enemy ? hidden : battle.State.B,
            PendingActions = new[] { new PendingAction(enemy, new CombatAction(CombatActionKind.EndWindow)) }
        } };
        Require(JsonSerializer.Serialize(original) == JsonSerializer.Serialize(CombatPlayerView.Create(mutated, human)),
            "Opponent's private hand, draw order or pending command changed the UI view.");
        var events = new[]
        {
            new CombatEvent(0, 0, "CardDrawn", enemy, "时光倒流"),
            new CombatEvent(0, 0, "SearchTargetSelected", enemy, "时光倒流"),
            new CombatEvent(0, 0, "CardPlayed", enemy, "攻击强化"),
            new CombatEvent(0, 0, "CardDrawn", human, "护盾")
        };
        var visible = CombatPlayerView.VisibleEvents(battle, human, events);
        Require(visible.Count == 2 && visible.All(e => e.CardId != "时光倒流") &&
            visible.Any(e => e.Player == enemy && e.Kind == "CardPlayed"), "Hidden draws leaked or public played cards disappeared.");
        Require(CombatPlayerView.Create(battle, new PlayerId("unrelated")) is null &&
            CombatPlayerView.VisibleEvents(battle, new PlayerId("unrelated"), events).Count == 0,
            "Unrelated battle data crossed the UI boundary.");
        var aiView = AiObservations.Combat(GameSession.Current!.Coordinator.CurrentState, battle, human);
        Require(aiView.OwnDeck.SequenceEqual(battle.SnapshotA.Player == human
                ? battle.SnapshotA.Cards.Select(c => c.CardId).OrderBy(n => n, StringComparer.Ordinal)
                : battle.SnapshotB.Cards.Select(c => c.CardId).OrderBy(n => n, StringComparer.Ordinal)),
            "Delegate did not receive its complete deck composition.");
    }

    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidDataException(message);
    }

    public override void _ExitTree()
    {
        _session?.Dispose();
        if (GameSession.Current == _session) GameSession.Current = null;
    }
}
