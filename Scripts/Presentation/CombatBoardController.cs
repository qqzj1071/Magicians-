using Godot;
using Magicians.Application;
using Magicians.Core.Common;
using Magicians.Core.Combat;
using Magicians.Core.AI;
using Magicians.Core.Match;

namespace Magicians.Presentation;

public partial class CombatBoardController : Control
{
    private Label _status = null!;
    private ColorRect _human = null!;
    private ColorRect _ai = null!;
    private ColorRect _projectile = null!;
    private VBoxContainer _actions = null!;
    private RichTextLabel _eventLog = null!;
    private RichTextLabel _missileLog = null!;
    private PackedScene _cardScene = null!;
    private string? _actionViewKey;
    private Button _delegateCombat = null!;
    private int _eventRound;
    private Button _selfStatus = null!;
    private Button _opponentStatus = null!;

    private readonly List<CombatEvent> _events = new();
    private bool _commandBusy;
    public void AppendEvents(IEnumerable<CombatEvent> events)
    {
        var session = GameSession.Current;
        if (session is null) return;
        if (_eventRound != session.Coordinator.CurrentState.Round)
        {
            _eventRound = session.Coordinator.CurrentState.Round;
            _events.Clear();
        }
        if (session.HumanBattle is { } battle)
            _events.AddRange(CombatPlayerView.VisibleEvents(battle, new PlayerId("human"), events));
    }

    public override void _Ready()
    {
        _status = GetNode<Label>("Panel/Column/Status");
        _human = GetNode<ColorRect>("Panel/Column/Arena/Human");
        _ai = GetNode<ColorRect>("Panel/Column/Arena/Ai");
        _projectile = GetNode<ColorRect>("Panel/Column/Arena/Projectile");
        _actions = GetNode<VBoxContainer>("Panel/Column/Actions");
        _cardScene = GD.Load<PackedScene>("res://Scenes/UI/CardView.tscn");
        var column = GetNode<VBoxContainer>("Panel/Column");
        _delegateCombat = new Button { Name = "DelegateCombat", Text = "本轮战斗由AI代理" };
        column.AddChild(_delegateCombat);
        column.MoveChild(_delegateCombat, _actions.GetIndex());
        _delegateCombat.Pressed += () =>
        {
            if (GameSession.Current?.DelegateHumanCombat() == true) Refresh();
        };
        var statusBar = new HBoxContainer { Name = "StatusButtons" };
        _selfStatus = new Button { Text = "我方状态" }; _opponentStatus = new Button { Text = "对手状态" };
        statusBar.AddChild(_selfStatus); statusBar.AddChild(_opponentStatus); column.AddChild(statusBar);
        _selfStatus.Pressed += () => OpenStatus(true);
        _opponentStatus.Pressed += () => OpenStatus(false);
        var position = _actions.GetIndex();
        var scroll = new ScrollContainer { SizeFlagsVertical = SizeFlags.ExpandFill, CustomMinimumSize = new Vector2(0, 320) };
        column.AddChild(scroll);
        column.MoveChild(scroll, position);
        _actions.Reparent(scroll);
        _actions.SizeFlagsHorizontal = SizeFlags.ExpandFill;
        GetNode<Control>("Panel/Column/Arena").CustomMinimumSize = new Vector2(0, 90);
        GetNode<Control>("Panel/Column/Arena").SizeFlagsVertical = SizeFlags.Fill;
        _status.SizeFlagsVertical = SizeFlags.Fill;
        _human.CustomMinimumSize = new Vector2(80, 80);
        _ai.CustomMinimumSize = new Vector2(80, 80);
        _eventLog = GetNode<RichTextLabel>("Panel/Column/Logs/CardColumn/EventLog");
        _missileLog = GetNode<RichTextLabel>("Panel/Column/Logs/MissileColumn/MissileLog");
        Refresh();
    }

    public void Refresh()
    {
        var session = GameSession.Current;
        if (session is null || !IsInstanceValid(_status)) return;
        var state = session.Coordinator.CurrentState;
        if (state.Phase is not (MatchPhase.Combat or MatchPhase.Settlement or MatchPhase.Finished))
        {
            _status.Text = "等待战斗实例";
            _events.Clear();
            _actionViewKey = null;
            return;
        }

        var manager = session.EnsureBattleInstances();

        var view = session.HumanBattle is { } humanBattle
            ? CombatPlayerView.Create(humanBattle, new PlayerId("human")) : null;
        _delegateCombat.Visible = view is { Phase: not CombatPhase.Finished } && state.Phase == MatchPhase.Combat;
        _delegateCombat.Disabled = session.IsHumanCombatDelegated;
        _delegateCombat.Text = session.IsHumanCombatDelegated ? "AI正在代理本轮剩余战斗" : "本轮战斗由AI代理";
        _status.Text = view is null ? "你已淘汰，正在结算剩余对局。" :
            $"你  攻击{view.Self.Attack} · 防御{view.Self.Defense} · 生命{view.Self.Life} · 护盾{view.Self.Shield} · 费用{view.Self.Energy}\n" +
            $"对手  攻击{view.Opponent.Attack} · 防御{view.Opponent.Defense} · 生命{view.Opponent.Life} · 护盾{view.Opponent.Shield}    行动值{view.ActionValue}";
        if (view?.Phase == CombatPhase.Finished && state.Phase == MatchPhase.Combat)
            _status.Text += "\n你的战斗已结束，正在后台结算另一组对战……";
        _projectile.Visible = view?.Phase == CombatPhase.Decision;
        if (view is not null)
        {
            _human.Modulate = LifeTint(view.Self.Life);
            _ai.Modulate = LifeTint(view.Opponent.Life);
        }
        _selfStatus.Visible = view is not null;
        _opponentStatus.Visible = view is not null;
        _eventLog.Text = CombatLogText.Exchanges(_events, new PlayerId("human"));
        var missileText = CombatLogText.Missiles(_events, new PlayerId("human"));
        if (_missileLog.Text != missileText) _missileLog.Text = missileText;
        RefreshActions(session, view, state);
    }

    private void RefreshActions(GameSession session, CombatPlayerView? view, MatchState match)
    {
        var key = $"{match.Round}:{match.Phase}:{view?.Revision}:{view?.CanAct}:{session.IsHumanCombatDelegated}";
        if (_actionViewKey == key) return;
        _actionViewKey = key;
        foreach (var child in _actions.GetChildren()) { _actions.RemoveChild(child); child.QueueFree(); }
        if (match.Phase != MatchPhase.Combat) return;
        if (view is not null && view.Phase != CombatPhase.Finished)
        {
            var human = view.Self;
            var battleId = view.Battle;
            var canAct = view.CanAct && !session.IsHumanCombatDelegated;
            var grid = new GridContainer { Columns = 5, SizeFlagsHorizontal = SizeFlags.ShrinkCenter };
            grid.AddThemeConstantOverride("h_separation", 12);
            grid.AddThemeConstantOverride("v_separation", 12);
            _actions.AddChild(grid);
            foreach (var card in view.OwnCards)
            {
                var definition = session.Cards.Get(card.CardId);
                var row = new VBoxContainer();
                var cardView = _cardScene.Instantiate<CardView>();
                var width = Mathf.Clamp(Mathf.Min((Size.X - 80) / 5, (Size.Y - 430) / 1.618f), 220, 300);
                cardView.CustomMinimumSize = new Vector2(width, width * 1.618f);
                row.AddChild(cardView);
                cardView.Bind(session.CardProfiles.Get(card.CardId), combat: true,
                    enchantmentApplied: humanBattleCardApplied(session, battleId, card.InstanceId));
                var button = new Button { Text = definition.Cost > human.Energy ? "费用不足" : "出牌" };
                button.Disabled = !canAct || definition.Cost > human.Energy;
                var instanceId = card.InstanceId;
                var revision = view.Revision;
                button.Pressed += () => PlayOrSearch(battleId, instanceId, revision);
                row.AddChild(button);
                grid.AddChild(row);
            }
            var end = new Button { Text = "结束当前出牌窗口" };
            end.Disabled = !canAct;
            end.Pressed += () => SubmitHuman(battleId, new CombatAction(CombatActionKind.EndWindow));
            _actions.AddChild(end);


        }

        if (view is null) _actions.AddChild(new Label { Text = "你已淘汰，正在结算剩余对局。" });
        else if (session.IsHumanCombatDelegated && view.Phase != CombatPhase.Finished)
            _actions.AddChild(new Label { Text = "AI根据你的完整牌组与当前局面自动出牌和检索；下一轮恢复手动。" });
        else if (!view.CanAct && view.Phase == CombatPhase.Decision)
            _actions.AddChild(new Label { Text = "对手正在决策，等待本步结算……" });
    }

    private static bool humanBattleCardApplied(GameSession session, BattleId battle, CardInstanceId card)
    {
        var instance = session.BattleInstances!.Instances[battle];
        var actor = instance.State.A.Player.Value == "human" ? instance.State.A : instance.State.B;
        return actor.FirstPlayed.Contains(card);
    }

    private void OpenStatus(bool self)
    {
        var session = GameSession.Current;
        if (session?.HumanBattle is not { } battle) return;
        var viewer = new PlayerId("human");
        var player = self ? viewer : (battle.Pairing.PlayerA == viewer ? battle.Pairing.PlayerB : battle.Pairing.PlayerA);
        var panel = new CombatStatusPanel { Transient = true, Exclusive = true };
        AddChild(panel); panel.Open(battle, player, session.Cards);
    }

    private void PlayOrSearch(BattleId battle, CardInstanceId card, long revision)
    {
        var manager = GameSession.Current!.EnsureBattleInstances();
        var search = manager.GetSearchSession(battle, new PlayerId("human"), card);
        if (search is null || search.Candidates.Count == 0)
        {
            SubmitHuman(battle, new CombatAction(CombatActionKind.PlayCard, card), revision);
            return;
        }
        var popup = new Window { Title = $"{search.CardId}：按顺序选择至多{search.MaximumSelections}张",
            Size = new Vector2I(560, 480), Transient = true, Exclusive = true };
        var column = new VBoxContainer();
        popup.AddChild(column);
        column.SetAnchorsAndOffsetsPreset(LayoutPreset.FullRect);
        var selected = new List<CardInstanceId>();
        var order = new Label { Text = "选择顺序决定置顶顺序" };
        column.AddChild(order);
        foreach (var candidate in search.Candidates)
        {
            var button = new CheckButton { Text = candidate.CardId };
            button.Toggled += enabled =>
            {
                if (enabled && selected.Count >= search.MaximumSelections) { button.SetPressedNoSignal(false); return; }
                if (enabled) selected.Add(candidate.InstanceId); else selected.Remove(candidate.InstanceId);
                order.Text = string.Join(" → ", selected.Select(id => search.Candidates.Single(c => c.InstanceId == id).CardId));
            };
            column.AddChild(button);
        }
        var confirm = new Button { Text = "确认出牌" };
        confirm.Pressed += () =>
        {
            if (search.MaximumSelections == 1 && selected.Count != 1) return;
            popup.QueueFree();
            SubmitHuman(battle, search.MaximumSelections > 1
                ? new CombatAction(CombatActionKind.PlayCard, card, SearchTargets: selected.ToArray())
                : new CombatAction(CombatActionKind.PlayCard, card, selected[0]), revision);
        };
        column.AddChild(confirm);
        popup.CloseRequested += () => popup.QueueFree();
        AddChild(popup);
        popup.PopupCentered();
    }

    private void SubmitHuman(BattleId battleId, CombatAction action, long? expectedRevision = null)
    {
        if (_commandBusy) return;
        _commandBusy = true;
        var session = GameSession.Current!;
        try
        {
            var manager = session.EnsureBattleInstances();
            var instance = manager.Instances[battleId];
            var human = new PlayerId("human");
            var accepted = session.SubmitCombat(new CombatCommand(battleId, human, expectedRevision ?? instance.State.Revision, action));
            if (!accepted.Accepted) { Refresh(); return; }
            AppendEvents(accepted.Events);
            TrySettleFinished(session);
            Refresh();
            GetParent().GetParent().GetParent<MatchViewController>().Refresh();
        }
        finally { _commandBusy = false; }
    }

    private static void TrySettleFinished(GameSession session)
    {
        var manager = session.EnsureBattleInstances();
        foreach (var instance in manager.Instances.Values.OrderBy(item => item.Pairing.BattleId.Value, StringComparer.Ordinal))
        {
            if (instance.State.Phase == CombatPhase.Finished &&
                !session.Coordinator.CurrentState.BattleResults.Any(result => result.Battle == instance.Pairing.BattleId))
                session.ApplyFinishedBattle(instance.Pairing.BattleId);
        }
    }

    private static Color LifeTint(int life)
    {
        var ratio = Mathf.Clamp((float)life / 1000f, 0.2f, 1f);
        return new Color(1f, ratio, ratio);
    }
}

