using Godot;
using Magicians.Application;
using Magicians.Core.AI;
using Magicians.Core.Cards;
using Magicians.Core.Combat;
using Magicians.Core.Common;
using Magicians.Core.Draft;
using Magicians.Core.Match;
using Magicians.Presentation;

namespace Magicians.Tests;

public partial class DraftUiRevisionRunner : Node
{
    public override async void _Ready()
    {
        try
        {
            var root = ProjectSettings.GlobalizePath("res://");
            var template = Slice1Scenario.Load(Path.Combine(root, "Data/slice1/scenario.json"));
            using var draftSession = GameSession.CreateScenario(root, template with { Round = 7, InitialStudyPoints = 100 });
            var session = draftSession;
            GameSession.Current = session;
            VerifyRouteCaps(session);
            VerifyBroadcasts(session);
            session.BeginDraft();
            var match = GD.Load<PackedScene>("res://Scenes/Match/Match.tscn").Instantiate<MatchViewController>();
            AddChild(match); match.SetProcess(false);
            var draft = match.GetNode<DraftBoardController>("Layout/Content/DraftBoard");
            var state = session.Coordinator.CurrentState; var human = new PlayerId("human");
            var buy = AiObservations.Draft(state, human, session.Cards).LegalActions.First(a => a.Kind == "buy");
            Accept(session.Coordinator.Submit(new BuyCardCommand(state.Id, human, buy.Slot!, new(state.EventSequence + 1))).Accepted, "Buy extra deletion-test card");
            var purchased = session.Coordinator.CurrentState.Players[human].Draft.Offers.Single(o => o.IsPurchased).Card;
            match.Refresh(); draft.OpenRemovalWindow();
            var window = draft.GetNode<Window>("RemovalWindow");
            var grid = window.GetNode<GridContainer>("Layout/Scroll/Cards");
            Accept(grid.GetChildCount() == 9, "Deletion popup must show every card, including protected cards");
            var remove = grid.GetChildren().OfType<VBoxContainer>().SelectMany(r => r.GetChildren().OfType<Button>())
                .Single(b => b.GetMeta("card_instance").AsString() == purchased.InstanceId.Value);
            await Capture("deletion-card-gallery.png");
            Accept(remove.Text == "删除" && !remove.Disabled, "Legal deletion card button");
            remove.EmitSignal(Button.SignalName.Pressed);
            Accept(session.Coordinator.CurrentState.Players[human].Deck.Cards.All(c => c.InstanceId != purchased.InstanceId) &&
                session.Coordinator.CurrentState.Players[human].Draft.RemovalCount == 1 && grid.GetChildCount() == 8 &&
                draft.GetNode<Button>("Panel/Column/RemoveCards").Text.Contains("已删除1张", StringComparison.Ordinal), "Exact selected card deletion and count refresh");
            Accept(grid.GetChildren().OfType<VBoxContainer>().SelectMany(r => r.GetChildren().OfType<Button>()).All(b => b.Disabled), "Minimum deck protection remains authoritative");
            var rarityColors = session.CardProfiles.All.GroupBy(p => p.Rarity).Select(g => CardView.RarityColor(g.Key)).ToArray();
            Accept(rarityColors.Distinct().Count() == rarityColors.Length, "Rarity labels need distinct colors");
            window.QueueFree(); await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);

            // A real low-life tournament: the human plays once and then ends
            // windows, the opponent continues playing; the second pair double KOs.
            using var reviewSession = GameSession.CreateScenario(root, template with { InitialTournamentLife = 1 });
            session = reviewSession; GameSession.Current = session; session.BeginDraft();
            foreach (var p in session.Coordinator.CurrentState.Players.Values.ToArray())
            {
                state = session.Coordinator.CurrentState;
                Accept(session.Coordinator.Submit(new FinishDraftCommand(state.Id, p.Id, new(state.EventSequence + 1))).Accepted, "Finish test draft");
            }
            var manager = session.EnsureBattleInstances(); var played = false;
            for (var step = 0; step < 600 && session.Coordinator.CurrentState.Phase == MatchPhase.Combat; step++)
                foreach (var id in manager.Instances.Keys.ToArray())
                {
                    foreach (var actor in new[] { manager.Instances[id].State.A.Player, manager.Instances[id].State.B.Player })
                    {
                        var battle = manager.Instances[id]; var combat = battle.State;
                        if (combat.Phase == CombatPhase.Finished || combat.EndedWindows.Contains(actor) || combat.PendingActions.Any(a => a.Player == actor)) continue;
                        var self = combat.A.Player == actor ? combat.A : combat.B;
                        var inHumanBattle = battle.Pairing.PlayerA == human || battle.Pairing.PlayerB == human;
                        var card = inHumanBattle && (actor != human || !played) ? self.CurrentPool.FirstOrDefault(c =>
                            session.Cards.Get(c.CardId).Cost <= self.Energy && !CombatCardExecution.IsSearch(c.CardId)) : null;
                        var action = card is null ? new CombatAction(CombatActionKind.EndWindow) : new CombatAction(CombatActionKind.PlayCard, card.InstanceId);
                        Accept(session.SubmitCombat(new CombatCommand(id, actor, combat.Revision, action)).Accepted, "History test play");
                        if (actor == human && card is not null) played = true;
                    }
                    if (manager.Instances[id].State.Phase == CombatPhase.Finished &&
                        session.Coordinator.CurrentState.BattleResults.All(b => b.Battle != id)) session.ApplyFinishedBattle(id);
                }
            Accept(session.Coordinator.CurrentState.Phase == MatchPhase.Settlement &&
                session.Coordinator.CurrentState.Players[human].TournamentLife <= 0, "Human elimination fixture");
            match.Refresh();
            var review = match.GetNode<BattleReviewPanel>("Layout/Content/BattleReview");
            Accept(review.Visible && session.RecordedBattles.Count == 2 && session.RecordedBattles.All(b => b.Result is not null), "Automatic elimination review");
            var history = session.RecordedBattles.Single(b => b.Pairing.PlayerA == human || b.Pairing.PlayerB == human);
            Accept(history.Plays.Any(p => p.Player == human) && history.Plays.Any(p => p.Player != human) &&
                history.Plays.All(p => p.Kind == "CardPlayed") && history.Plays.GroupBy(p => p.Revision).Count() > 3, "Full history, rather than only the recent log");
            session.AdvanceRound(); match.Refresh();
            Accept(session.Coordinator.CurrentState.Phase == MatchPhase.Finished && review.Visible, "Final tournament review");
            await Capture("round-by-round-review.png");
            GD.Print("DRAFT_UI_REVISION_OK route-cap=80-cases broadcast=4-players rarity=5-colors deletion=exact-instance history=elimination-and-finish");
            match.QueueFree(); await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            GameSession.Current = null; GetTree().Quit();
        }
        catch (Exception error) { GD.PrintErr("DRAFT_UI_REVISION_FAILED " + error); GetTree().Quit(1); }
    }

    private static void VerifyRouteCaps(GameSession session)
    {
        var cards = session.Cards; var pool = session.FullCardPool;
        var original = session.Coordinator.CurrentState.Players.Values.First();
        foreach (var round in new[] { 10, 12 })
        foreach (var element in new[] { "fire", "water", "earth", "wind", "poison" })
        for (var seed = 0; seed < 8; seed++)
        {
            var route = cards.All.First(c => c.Element == element && c.Kind == CardKind.RouteLegendary);
            var p = original with { Deck = original.Deck with { Cards = original.Deck.Cards.Append(new(new("cap-owned-route"), route.Name, original.Id)).ToArray() },
                Draft = DraftState.Initial(round, 100) with { SpecializationElement = element, RouteLegendaryId = route.Name } };
            var stock = pool.OfferPool.ToDictionary(c => c.CardId, c => c.Count); stock[route.Name]--;
            var unseen = stock.Where(c => cards.Get(c.Key).Rarity == CardRarity.Legendary).ToDictionary(c => c.Key, c => c.Value);
            var templates = new Dictionary<PlayerId, int[]> { [p.Id] = Enumerable.Repeat(3, 8).ToArray() };
            var allocator = new DraftOfferAllocator(cards, pool.DraftRules!);
            var first = allocator.Generate(new[] { p }, templates, round, false, stock, unseen, new SeededRandom(seed));
            var firstOffers = first.Offers[p.Id];
            Accept(firstOffers.All(o => p.Deck.Cards.All(owned => owned.CardId != o.Card.CardId)), "Allocator offered a card already in the owner's deck");
            Accept(firstOffers.Count(o => cards.Get(o.Card.CardId).Kind == CardKind.RouteLegendary) == 1, "First face route cap with available inventory");
            foreach (var offer in firstOffers) stock[offer.Card.CardId]++;
            p = p with { Draft = p.Draft with { Offers = firstOffers, ShownLegendaryIds = first.SeenNames[p.Id] } };
            var refresh = allocator.Generate(new[] { p }, templates, round, true, stock, unseen, new SeededRandom(seed + 100));
            Accept(refresh.Offers[p.Id].All(o => cards.Get(o.Card.CardId).Kind != CardKind.RouteLegendary), "Refresh bypassed the full-round cap");
            Accept(stock.Values.All(n => n >= 0), "Cap allocation inventory overissue");
        }
    }

    private static void VerifyBroadcasts(GameSession session)
    {
        var state = session.Coordinator.CurrentState;
        var spec = session.Cards.All.First(c => c.Kind == CardKind.Specialization);
        var route = session.Cards.All.First(c => c.Kind == CardKind.RouteLegendary);
        var events = state.Players.Values.SelectMany((p, i) => new GameEvent[]
        {
            new DraftRuleChangedEvent(state.Id, 1, i * 3 + 1, "", p.Id, "Specialization", new[] { spec.Name }),
            new DraftRuleChangedEvent(state.Id, 1, i * 3 + 2, "", p.Id, "Route", new[] { route.Name }),
            new DraftRuleChangedEvent(state.Id, 1, i * 3 + 3, "", p.Id, "ReplaceRoute", new[] { route.Name })
        }).ToArray();
        var lines = DraftBroadcastText.Lines(state with { EventLog = events }, session.Cards).ToArray();
        Accept(lines.Length == 12 && state.Players.Values.All(p => lines.Count(l => l.Contains(p.PublicInfo.DisplayName, StringComparison.Ordinal)) == 3), "All four participants' choices need broadcasts");
    }

    private static void Accept(bool condition, string message)
    {
        if (!condition) throw new InvalidDataException(message);
    }

    private async Task Capture(string name)
    {
        if (!OS.GetCmdlineUserArgs().Contains("--capture-ui")) return;
        await ToSignal(GetTree().CreateTimer(0.25), SceneTreeTimer.SignalName.Timeout);
        await ToSignal(RenderingServer.Singleton, RenderingServer.SignalName.FramePostDraw);
        GetViewport().GetTexture().GetImage().SavePng(ProjectSettings.GlobalizePath("res://../runtime/" + name));
    }
}
