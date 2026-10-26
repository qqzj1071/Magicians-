using Magicians.Core.AI;
using Magicians.Core.Cards;
using Magicians.Core.Common;
using Magicians.Core.Match;

namespace Magicians.Tests;

public static class DraftRulesRegression
{
    public static void Run(CardDatabase cards, Slice1CardPool pool, Slice1CardPool? fullPool = null)
    {
        var coordinator = new MatchCoordinator(cards, pool);
        var state = coordinator.Start(new StartMatchSetup(
            new MatchId("draft-rules-regression"), 20261025,
            new[]
            {
                new PlayerSetup(new PlayerId("human"), PlayerKind.Human, "Player"),
                new PlayerSetup(new PlayerId("ai-1"), PlayerKind.Ai, "AI 1"),
                new PlayerSetup(new PlayerId("ai-2"), PlayerKind.Ai, "AI 2"),
                new PlayerSetup(new PlayerId("ai-3"), PlayerKind.Ai, "AI 3")
            },
            Round: 4,
            InitialStudyPoints: 3,
            AllowRefresh: true,
            AllowRemove: true,
            AllowSpecialization: true,
            AllowRouteSelection: true));
        Accept(coordinator, new BeginDraftCommand(state.Id, new PlayerId("human"), Next(coordinator)));

        var human = new PlayerId("human");
        var refresh = Accept(coordinator, new RefreshOffersCommand(
            coordinator.CurrentState.Id, human, Next(coordinator)));
        if (coordinator.CurrentState.Players[human].Draft.RefreshesUsed != 1 ||
            !refresh.Events.OfType<DraftRuleChangedEvent>().Any(eventItem => eventItem.Action == "Refresh"))
            throw new InvalidDataException("Refresh rule did not consume exactly one refresh and one study point.");

        var offer = coordinator.CurrentState.Players[human].Draft.Offers.First();
        Accept(coordinator, new BuyCardCommand(coordinator.CurrentState.Id, human, offer.SlotId, Next(coordinator)));
        var purchased = coordinator.CurrentState.Players[human].Deck.Cards.Last();
        Accept(coordinator, new RemoveCardCommand(coordinator.CurrentState.Id, human, purchased.InstanceId, Next(coordinator)));
        if (coordinator.CurrentState.Players[human].Deck.Cards.Any(card => card.InstanceId == purchased.InstanceId) ||
            coordinator.CurrentState.Players[human].Draft.RemovalCount != 1)
            throw new InvalidDataException("Removal did not return the purchased entity to the pool.");

        var specialization = coordinator.Submit(new ChooseSpecializationCommand(
            coordinator.CurrentState.Id, human, "fire", "不灭烈焰", Next(coordinator)));
        if (specialization.Accepted || specialization.Rejection?.Code != "SpecializationRequirement")
            throw new InvalidDataException("Specialization accepted without three matching enchantments.");

        var route = coordinator.Submit(new ChooseRouteCommand(
            coordinator.CurrentState.Id, human, "余烬之核", Next(coordinator)));
        if (route.Accepted || route.Rejection?.Code != "RouteRequiresSpecialization")
            throw new InvalidDataException("Route accepted without a matching specialization.");

        var legendaryCoordinator = new MatchCoordinator(cards, fullPool ?? pool);
        var legendaryState = legendaryCoordinator.Start(new StartMatchSetup(
            new MatchId("legendary-pity-regression"), 20261025,
            new[]
            {
                new PlayerSetup(new PlayerId("human"), PlayerKind.Human, "Player"),
                new PlayerSetup(new PlayerId("ai-1"), PlayerKind.Ai, "AI 1"),
                new PlayerSetup(new PlayerId("ai-2"), PlayerKind.Ai, "AI 2"),
                new PlayerSetup(new PlayerId("ai-3"), PlayerKind.Ai, "AI 3")
            },
            Round: 10, InitialStudyPoints: 4, AllowRefresh: true, AllowRemove: true,
            AllowSpecialization: true, AllowRouteSelection: true));
        Accept(legendaryCoordinator, new BeginDraftCommand(legendaryState.Id, new PlayerId("human"), Next(legendaryCoordinator)));
        var pityOffers = legendaryCoordinator.CurrentState.Players[new PlayerId("human")].Draft.Offers;
        if (!pityOffers.Any(offer => cards.Get(offer.Card.CardId).Kind == CardKind.RouteLegendary))
            throw new InvalidDataException("Round 10 legendary pity did not offer a route card before specialization.");

        var firstRound = new FirstRoundPairingService();
        var first = firstRound.CreateFirstRound(coordinator.CurrentState.Players);
        var next = firstRound.CreateNextRound(coordinator.CurrentState.Players, first, 2);
        if (next.Any(pair => first.Any(previous => SamePair(pair, previous))))
            throw new InvalidDataException("The deterministic next-round pairing repeated an opponent.");

        var ghostPlayers = coordinator.CurrentState.Players.ToDictionary(pair => pair.Key, pair => pair.Value);
        var eliminated = ghostPlayers[new PlayerId("ai-3")];
        ghostPlayers[eliminated.Id] = eliminated with { Kind = PlayerKind.Ghost, TournamentLife = 0 };
        var ghostRound = firstRound.CreateNextRound(ghostPlayers, first, 2);
        if (ghostRound.Count != 2 || !ghostRound.Any(pair => pair.PlayerA == eliminated.Id || pair.PlayerB == eliminated.Id))
            throw new InvalidDataException("An odd survivor count did not use a deterministic ghost pairing.");
    }

    private static bool SamePair(Pairing left, Pairing right) =>
        (left.PlayerA == right.PlayerA && left.PlayerB == right.PlayerB) ||
        (left.PlayerA == right.PlayerB && left.PlayerB == right.PlayerA);

    private static CommandSequence Next(MatchCoordinator coordinator) =>
        new(coordinator.CurrentState.EventSequence + 1);

    private static CommandResult<MatchState> Accept(MatchCoordinator coordinator, IGameCommand command)
    {
        var result = coordinator.Submit(command);
        if (!result.Accepted)
            throw new InvalidDataException($"Draft rules command rejected: {result.Rejection?.Code}");
        return result;
    }
}
