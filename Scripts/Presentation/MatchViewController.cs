using Godot;
using Magicians.Core.Cards;
using Magicians.Application;
using Magicians.Core.Common;
using Magicians.Core.Combat;
using Magicians.Core.Match;

namespace Magicians.Presentation;

public partial class MatchViewController : Control
{
    private Label _standings = null!;
    private Label _phaseLabel = null!;
    private Label _lifeLabel = null!;
    private Label _pairingLabel = null!;
    private Control _draftBoard = null!;
    private Control _combatBoard = null!;
    private Button _nextRound = null!;
    private double _tickTime;
    private Label _battleBroadcast = null!;
    private Label _draftBroadcast = null!;
    private BattleReviewPanel _review = null!;
    private Button _reviewButton = null!;
    private bool _reviewOpened;
    private bool _showReview;
    private bool _watchingAi;
    private Button _watchAi = null!;
    private Button _restart = null!;
    private Button _exit = null!;

    public override void _Ready()
    {
        _phaseLabel = GetNode<Label>("Layout/Header/Phase");
        _lifeLabel = GetNode<Label>("Layout/Header/Life");
        _pairingLabel = GetNode<Label>("Layout/Header/Pairings");
        _battleBroadcast = new Label { Name = "BattleBroadcast", AutowrapMode = TextServer.AutowrapMode.Off, ClipText = true, CustomMinimumSize = new Vector2(0, 28) };
        var layout = GetNode<VBoxContainer>("Layout");
        layout.AddChild(_battleBroadcast);
        layout.MoveChild(_battleBroadcast, 1);
        _draftBroadcast = new Label
        {
            Name = "DraftBroadcast",
            CustomMinimumSize = new Vector2(0, 28),
            SizeFlagsHorizontal = SizeFlags.ExpandFill,
            AutowrapMode = TextServer.AutowrapMode.Off,
            ClipText = true
        };
        layout.AddChild(_draftBroadcast); layout.MoveChild(_draftBroadcast, 2);
        _standings = new Label { Name = "FinalStandings", AutowrapMode = TextServer.AutowrapMode.WordSmart };
        layout.AddChild(_standings); layout.MoveChild(_standings, 3);
        _draftBoard = GetNode<Control>("Layout/Content/DraftBoard");
        _combatBoard = GetNode<Control>("Layout/Content/CombatBoard");
        _review = new BattleReviewPanel { Name = "BattleReview", SizeFlagsHorizontal = SizeFlags.ExpandFill, SizeFlagsVertical = SizeFlags.ExpandFill };
        GetNode("Layout/Content").AddChild(_review);
        _reviewButton = new Button { Text = "逐轮出牌复盘" }; GetNode("Layout/Header").AddChild(_reviewButton);
        _reviewButton.Pressed += () => { _showReview = !_showReview; Refresh(); };
        _nextRound = new Button { Text = "查看结算并继续赛事" };
        GetNode("Layout/Header").AddChild(_nextRound);
        _nextRound.Pressed += () => { GameSession.Current?.AdvanceRound(); Refresh(); };
        var actions = new HBoxContainer { Name = "EndActions" };
        _watchAi = new Button { Text = "观看 AI 对局直到冠军" };
        _restart = new Button { Text = "重新开始一局" };
        _exit = new Button { Text = "退出游戏" };
        actions.AddChild(_watchAi); actions.AddChild(_restart); actions.AddChild(_exit);
        GetNode("Layout/Header").AddChild(actions);
        _watchAi.Pressed += StartWatchingAi;
        _restart.Pressed += RestartGame;
        _exit.Pressed += ExitGame;
        var settings = new DisplaySettingsDialog(); AddChild(settings);
        var display = new Button { Text = "显示设置" }; GetNode("Layout/Header").AddChild(display);
        display.Pressed += () => settings.PopupCentered(new Vector2I(560, 180));
        Refresh();
    }

    public override void _Process(double delta)
    {
        _tickTime += delta;
        if (_tickTime < 0.05 || GameSession.Current is null) return;
        _tickTime = 0;
        var phase = GameSession.Current.Coordinator.CurrentState.Phase;
        if (_watchingAi)
        {
            try
            {
                if (phase == MatchPhase.Settlement) GameSession.Current.AdvanceRound();
                else if (phase is MatchPhase.Combat or MatchPhase.Draft) GameSession.Current.TickAutonomous();
            }
            catch (Exception error) { _phaseLabel.Text = "AI观战暂停：" + error.Message; }
            Refresh();
            return;
        }
        if (phase is not (MatchPhase.Combat or MatchPhase.Draft)) return;
        var before = GameSession.Current.Coordinator.CurrentState.EventSequence;
        var humanBattleState = GameSession.Current.HumanBattle?.State;
        IReadOnlyList<CombatEvent> events;
        try { events = GameSession.Current.TickAutonomous(); }
        catch (Exception error) { _phaseLabel.Text = "AI推理暂停：" + error.Message; return; }
        if (GameSession.Current.AiError is { } aiError) { _phaseLabel.Text = "AI推理暂停：" + aiError; return; }
        if (_combatBoard is CombatBoardController combat) combat.AppendEvents(events);
        if (events.Count > 0 || before != GameSession.Current.Coordinator.CurrentState.EventSequence ||
            !ReferenceEquals(humanBattleState, GameSession.Current.HumanBattle?.State)) Refresh();
    }

    public void Refresh()
    {
        var session = GameSession.Current;
        if (session is null) return;
        session.SaveLocalRecord();
        var state = session.Coordinator.CurrentState;
        if (state.Phase == MatchPhase.Settlement && state.Players.Values.Count(p => p.TournamentLife > 0) <= 1)
        {
            session.AdvanceRound();
            state = session.Coordinator.CurrentState;
        }
        var canReview = state.Phase == MatchPhase.Finished || state.Players[new PlayerId("human")].TournamentLife <= 0;
        if (canReview && !_reviewOpened) { _reviewOpened = true; _showReview = true; }
        _reviewButton.Visible = canReview;
        _review.Visible = canReview && _showReview;
        _reviewButton.Text = _review.Visible ? "返回赛事" : "逐轮出牌复盘";
        _draftBroadcast.Text = string.Join("\n", DraftBroadcastText.Lines(state, session.Cards));
        _draftBroadcast.Visible = state.Phase == MatchPhase.Draft && _draftBroadcast.Text.Length > 0 && !_review.Visible;
        var resultRound = state.Phase == MatchPhase.Combat ? state.Round - 1 :
            session.BattleAnnouncements.LastOrDefault()?.Round;
        var results = session.BattleAnnouncements.Where(a => a.Round == resultRound).ToArray();
        _battleBroadcast.Text = string.Join("；", results.Select(a => a.Text));
        _battleBroadcast.Visible = results.Length > 0 && !_review.Visible;
        _phaseLabel.Text = $"第{state.Round}轮 · 阶段：{state.Phase}";
        _nextRound.Visible = state.Phase == MatchPhase.Settlement;
        _watchAi.Visible = canReview && state.Phase != MatchPhase.Finished;
        _restart.Visible = state.Phase == MatchPhase.Finished || canReview;
        _exit.Visible = state.Phase == MatchPhase.Finished || canReview;
        _watchAi.Disabled = _watchingAi;
        if (_watchingAi) _watchAi.Text = "AI观战进行中";
        _standings.Visible = state.Phase == MatchPhase.Finished;
        if (_standings.Visible)
            _standings.Text = string.Join("\n", TournamentStandings.Calculate(state).Select(p =>
                $"第{p.Place}名 {state.Players[p.Player].PublicInfo.DisplayName} · " +
                (p.EliminatedRound is { } round ? $"第{round}轮淘汰，淘汰结算血量 {p.RemainingLife}" : $"存活夺冠，剩余血量 {p.RemainingLife}")));
        if (state.Phase == MatchPhase.Finished)
        {
            var champions = TournamentStandings.Champions(state);
            _phaseLabel.Text = (champions.Count == 1 ? "冠军：" : "并列冠军：") +
                string.Join("、", champions.Select(id => state.Players[id].PublicInfo.DisplayName));
            _pairingLabel.Text = "赛事已结束";
        }
        _lifeLabel.Text = string.Join("   ", state.Players.Values
            .OrderBy(player => player.Id.Value, StringComparer.Ordinal)
            .Select(player => $"{player.PublicInfo.DisplayName}{(player.Draft.SpecializationElement is { } element ? "·" + CardPresentationCatalog.ElementLabel(element) : "")}{(player.Draft.RouteLegendaryId is { } route ? "·" + route : "")} {player.TournamentLife}"));
        if (state.Phase != MatchPhase.Finished) _pairingLabel.Text = state.Pairings.Count == 0
            ? "配对：等待公布"
            : "配对：" + string.Join(" / ", state.Pairings.Select(pair => $"{pair.PlayerA} vs {pair.PlayerB}"));
        _draftBoard.Visible = state.Phase == MatchPhase.Draft && !_review.Visible;
        _combatBoard.Visible = (state.Phase is MatchPhase.Combat or MatchPhase.Settlement or MatchPhase.Finished) && !_review.Visible;
        if (_combatBoard.Visible && session.BattleInstances is null)
            session.EnsureBattleInstances();
        if (_draftBoard.Visible && _draftBoard is DraftBoardController draft) draft.Refresh();
        if (_combatBoard.Visible && _combatBoard is CombatBoardController combat) combat.Refresh();
        if (_review.Visible) _review.Refresh();
    }

    private void StartWatchingAi()
    {
        if (GameSession.Current is null) return;
        _watchingAi = true;
        _showReview = false;
        _reviewOpened = false;
        _phaseLabel.Text = "AI观战进行中：将自动推进至冠军产生";
        Refresh();
    }

    public void WatchAiToChampion() => StartWatchingAi();
    public bool IsWatchingAi => _watchingAi;

    private void RestartGame()
    {
        if (GetParent() is BootController boot) boot.StartGame();
    }

    private void ExitGame()
    {
        if (GetParent() is BootController boot) boot.ExitGame();
        else GetTree().Quit();
    }
}
