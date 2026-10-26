using Godot;
using Magicians.Application;
using Magicians.Core.AI;
using Magicians.Core.Common;
using Magicians.Core.Match;

namespace Magicians.Presentation;

public partial class DraftBoardController : Control
{
    private VBoxContainer _offers = null!;
    private Label _study = null!;
    private Button _finish = null!;
    private bool _commandBusy;
    private PackedScene _cardScene = null!;
    private GridContainer? _cardGrid;
    private Button _removeCards = null!;
    private Window? _removeWindow;
    private VBoxContainer _actions = null!;
    private HBoxContainer _refreshActions = null!;

    public override void _Ready()
    {
        _offers = GetNode<VBoxContainer>("Panel/Column/Offers");
        _cardScene = GD.Load<PackedScene>("res://Scenes/UI/CardView.tscn");
        var column = GetNode<VBoxContainer>("Panel/Column");
        GetNode<Control>("Panel/Column/CardPreview").Visible = false;
        GetNode<Control>("Panel/Column/Title").Visible = false;
        var position = _offers.GetIndex();
        var scroll = new ScrollContainer { SizeFlagsVertical = SizeFlags.ExpandFill, CustomMinimumSize = new Vector2(0, 220) };
        column.AddChild(scroll);
        column.MoveChild(scroll, position);
        _offers.Reparent(scroll);
        _offers.SizeFlagsHorizontal = SizeFlags.ExpandFill;
        _actions = new VBoxContainer { Name = "DraftActions" };
        _refreshActions = new HBoxContainer { Name = "RefreshActions" };
        var removeActions = new HBoxContainer { Name = "RemoveActions" };
        var finishActions = new HBoxContainer { Name = "FinishActions" };
        column.AddChild(_actions);
        _actions.AddChild(_refreshActions);
        _actions.AddChild(removeActions);
        _actions.AddChild(finishActions);
        _removeCards = new Button { Name = "RemoveCards", Text = "删牌（本轮已删除0张）" };
        removeActions.AddChild(_removeCards);
        _removeCards.Pressed += OpenRemovalWindow;
        _study = GetNode<Label>("Panel/Column/Study");
        _finish = GetNode<Button>("Panel/Column/Finish");
        _finish.Reparent(finishActions);
        _finish.Pressed += FinishDraft;
        Resized += ResizeCards;
        Refresh();
    }

    public void Refresh()
    {
        var session = GameSession.Current;
        if (session is null || !IsInstanceValid(_offers)) return;
        foreach (var child in _offers.GetChildren()) { _offers.RemoveChild(child); child.QueueFree(); }
        var state = session.Coordinator.CurrentState;
        if (!state.Players.TryGetValue(new PlayerId("human"), out var player)) return;
        _finish.Disabled = player.TournamentLife <= 0 || player.Draft.IsCompleted || state.Phase != MatchPhase.Draft;
        _study.Text = $"研习点：{player.Draft.StudyPoints}";
        _removeCards.Text = $"删牌（本轮已删除{player.Draft.RemovalCount}张）";
        var removalAvailableThisRound = state.Round >= 4;
        _removeCards.Visible = removalAvailableThisRound;
        _removeCards.Disabled = !removalAvailableThisRound || state.Phase != MatchPhase.Draft || player.Draft.IsCompleted || player.TournamentLife <= 0;
        _removeCards.Modulate = !removalAvailableThisRound || player.Draft.FreePurchaseUsed ? Colors.White : new Color("ffd166");
        _removeCards.TooltipText = !player.Draft.FreePurchaseUsed
            ? "本轮免费购买资格尚未使用；删牌按钮已高亮"
            : "查看牌组并删除符合规则的卡牌";
        if (_removeWindow is not null && IsInstanceValid(_removeWindow)) RefreshRemovalWindow();
        var legal = AiObservations.Draft(state, player.Id, session.Cards).LegalActions;
        var grid = new GridContainer { Columns = 4, SizeFlagsHorizontal = SizeFlags.ShrinkCenter };
        _cardGrid = grid;
        grid.AddThemeConstantOverride("h_separation", 12);
        grid.AddThemeConstantOverride("v_separation", 12);
        _offers.AddChild(grid);
        foreach (var offer in player.Draft.Offers)
        {
            var row = new VBoxContainer();
            var view = _cardScene.Instantiate<CardView>();
            row.AddChild(view);
            var buy = new Button { Text = offer.IsPurchased ? "已购买" : offer.IsSkipped ? "已跳过" : "购买" };
            var definition = session.Cards.Get(offer.Card.CardId);
            var free = !player.Draft.FreePurchaseUsed && ((state.Round <= 3 && definition.Rarity == Magicians.Core.Cards.CardRarity.Common) ||
                (state.Round is >= 4 and <= 6 && definition.Rarity is Magicians.Core.Cards.CardRarity.Common or Magicians.Core.Cards.CardRarity.Rare));
            var purchaseActions = legal.Where(a => a.Kind == "buy" && a.Slot == offer.SlotId).ToArray();
            buy.Disabled = offer.IsResolved || purchaseActions.Length == 0 || player.Draft.IsCompleted;
            buy.TooltipText = definition.Text;
            view.Bind(session.CardProfiles.Get(offer.Card.CardId), offer.Cost, free && !offer.IsResolved);
            var slot = offer.SlotId;
            buy.Pressed += () =>
            {
                if (purchaseActions.Any(a => string.IsNullOrEmpty(a.Replace))) { Buy(slot); return; }
                var choice = new AcceptDialog { Title = "选择要替换的传奇牌" }; AddChild(choice);
                var choices = new VBoxContainer(); choice.AddChild(choices);
                foreach (var action in purchaseActions)
                {
                    var old = player.Deck.Cards.Single(c => c.InstanceId.Value == action.Replace);
                    var select = new Button { Text = $"替换 {old.CardId}（{action.Cost}研习点）" }; choices.AddChild(select);
                    select.Pressed += () => { Buy(slot, new CardInstanceId(action.Replace!)); choice.QueueFree(); };
                }
                choice.CloseRequested += choice.QueueFree;
                choice.PopupCentered(new Vector2I(520, 240));
            };
            row.AddChild(buy);
            grid.AddChild(row);
        }
        ResizeCards();
        foreach (var child in _refreshActions.GetChildren()) { _refreshActions.RemoveChild(child); child.QueueFree(); }
        if (state.Phase != MatchPhase.Draft || player.Draft.IsCompleted || player.TournamentLife <= 0) return;
        if (legal.Any(a => a.Kind == "refresh"))
            AddAction("刷新候选（1研习点）", () => RunCommand((id, sequence) => new RefreshOffersCommand(id, player.Id, sequence)));
        if (player.Draft.SpecializationElement is null)
            foreach (var definition in session.Cards.All.Where(c => c.Kind == Magicians.Core.Cards.CardKind.Specialization))
            {
                if (player.Deck.Cards.Count(c => session.Cards.Get(c.CardId).Element == definition.Element && session.Cards.Get(c.CardId).Layers > 0) < 3) continue;
                AddAction($"选择专精：{definition.Name}", () => RunCommand((id, sequence) =>
                    new ChooseSpecializationCommand(id, player.Id, definition.Element, definition.Name, sequence)));
            }
        if (session.CardPool.StarterCardsConsumePool && player.Draft.SpecializationElement is { } element)
            foreach (var definition in session.Cards.All.Where(c => c.Kind == Magicians.Core.Cards.CardKind.RouteLegendary && c.Element == element &&
                         c.Name != player.Draft.RouteLegendaryId && state.SharedCardInventory.GetValueOrDefault(c.Name) > 0))
                AddAction($"{(player.Draft.RouteLegendaryId is null ? "选择" : "替换")}路线：{definition.Name}", () => RunCommand((id, sequence) =>
                    player.Draft.RouteLegendaryId is { } oldRoute
                        ? new ReplaceRouteCommand(id, player.Id, oldRoute, definition.Name, sequence)
                        : new ChooseRouteCommand(id, player.Id, definition.Name, sequence)));
    }

    private void AddAction(string title, Action action)
    {
        var button = new Button { Text = title };
        button.Pressed += action;
        _refreshActions.AddChild(button);
    }

    public void OpenRemovalWindow()
    {
        if (_removeCards.Disabled) return;
        if (_removeWindow is not null && IsInstanceValid(_removeWindow)) return;
        _removeWindow = new Window { Name = "RemovalWindow", Title = "查看牌组并删除卡牌", Transient = true, Exclusive = true };
        var column = new VBoxContainer { Name = "Layout" };
        _removeWindow.AddChild(column);
        column.SetAnchorsAndOffsetsPreset(LayoutPreset.FullRect);
        column.AddChild(new Label { Name = "Summary", AutowrapMode = TextServer.AutowrapMode.WordSmart });
        var scroll = new ScrollContainer { Name = "Scroll", SizeFlagsVertical = SizeFlags.ExpandFill, HorizontalScrollMode = ScrollContainer.ScrollMode.Disabled };
        column.AddChild(scroll);
        var grid = new GridContainer { Name = "Cards", Columns = 4, SizeFlagsHorizontal = SizeFlags.ExpandFill };
        grid.AddThemeConstantOverride("h_separation", 12); grid.AddThemeConstantOverride("v_separation", 12);
        scroll.AddChild(grid);
        var close = new Button { Text = "完成" }; column.AddChild(close);
        var window = _removeWindow;
        close.Pressed += window.QueueFree;
        window.CloseRequested += window.QueueFree;
        AddChild(window);
        RefreshRemovalWindow();
        window.PopupCentered(new Vector2I(Math.Min(1360, (int)GetViewportRect().Size.X - 48), Math.Min(860, (int)GetViewportRect().Size.Y - 48)));
    }

    private void RefreshRemovalWindow()
    {
        var session = GameSession.Current!;
        var state = session.Coordinator.CurrentState;
        var player = state.Players[new PlayerId("human")];
        var legal = AiObservations.Draft(state, player.Id, session.Cards).LegalActions;
        var limit = state.Round <= 3 ? 0 : state.Round <= 6 ? 1 : 2;
        _removeWindow!.GetNode<Label>("Layout/Summary").Text =
            $"本轮已删除{player.Draft.RemovalCount}/{limit}张 · 研习点{player.Draft.StudyPoints} · 当前{player.Deck.Cards.Count}张。灰色按钮表示本轮不可删除；传奇、专精、最少8张及主系保护规则仍生效。";
        var grid = _removeWindow.GetNode<GridContainer>("Layout/Scroll/Cards");
        foreach (var child in grid.GetChildren()) { grid.RemoveChild(child); child.QueueFree(); }
        foreach (var card in player.Deck.Cards)
        {
            var row = new VBoxContainer { SizeFlagsHorizontal = SizeFlags.ExpandFill };
            var view = _cardScene.Instantiate<CardView>(); row.AddChild(view);
            view.Bind(session.CardProfiles.Get(card.CardId), combat: true);
            var action = legal.FirstOrDefault(a => a.Kind == "remove" && a.Card == card.InstanceId.Value);
            var button = new Button { Text = "删除", Disabled = action is null || state.Phase != MatchPhase.Draft || player.Draft.IsCompleted,
                TooltipText = action is null ? "当前不符合删牌规则" : $"删除【{card.CardId}】：{action.Cost}研习点" };
            button.SetMeta("card_instance", card.InstanceId.Value);
            button.Pressed += () => RunCommand((id, sequence) => new RemoveCardCommand(id, player.Id, card.InstanceId, sequence));
            row.AddChild(button); grid.AddChild(row);
        }
    }

    private void ResizeCards()
    {
        if (_cardGrid is null || !IsInstanceValid(_cardGrid)) return;
        var width = Mathf.Clamp(Mathf.Min((Size.X - 60) / 4, (Size.Y - 300) / (2 * 1.618f)), 190, 320);
        foreach (var row in _cardGrid.GetChildren().OfType<VBoxContainer>())
            foreach (var card in row.GetChildren().OfType<CardView>())
                card.CustomMinimumSize = new Vector2(width, width * 1.618f);
    }

    private void RunCommand(Func<MatchId, CommandSequence, IGameCommand> create)
    {
        if (_commandBusy) return;
        _commandBusy = true;
        try
        {
            var session = GameSession.Current!;
            var state = session.Coordinator.CurrentState;
            var result = session.Coordinator.Submit(create(state.Id, new(state.EventSequence + 1)));
            GetMatchView().Refresh();
            if (!result.Accepted) _study.Text += " · " + result.Rejection?.Message;
        }
        finally { _commandBusy = false; }
    }

    private void Buy(string slot, CardInstanceId? replace = null)
    {
        if (_commandBusy) return;
        _commandBusy = true;
        var session = GameSession.Current!;
        try
        {
            var state = session.Coordinator.CurrentState;
            var result = session.Coordinator.Submit(new BuyCardCommand(
                state.Id, new PlayerId("human"), slot, new CommandSequence(state.EventSequence + 1)) { ReplaceCard = replace });
            Refresh();
            GetMatchView().Refresh();
            if (!result.Accepted) _study.Text += " · " + result.Rejection?.Message;
        }
        finally { _commandBusy = false; }
    }

    private void FinishDraft()
    {
        if (_commandBusy) return;
        _commandBusy = true;
        var session = GameSession.Current!;
        try
        {
            var state = session.Coordinator.CurrentState;
            var human = new PlayerId("human");
            if (!state.Players[human].Draft.IsCompleted)
                session.Coordinator.Submit(new FinishDraftCommand(
                    state.Id, human, new CommandSequence(state.EventSequence + 1)));
            GetMatchView().Refresh();
        }
        finally { _commandBusy = false; }
    }

    private MatchViewController GetMatchView() =>
        GetParent().GetParent().GetParent<MatchViewController>();
}

