using Magicians.Core.AI;
using Magicians.Core.Cards;
using Magicians.Core.Common;
using Magicians.Core.Draft;
using Magicians.Core.Match;

namespace Magicians.Tests;

public static class DraftEconomyRegression
{
    private static readonly PlayerId Human = new("human");
    public static void Run(CardDatabase cards, Slice1CardPool pool)
    {
        for (var round = 1; round <= 20; round++)
        {
            var rare = cards.All.First(c => c.Rarity == CardRarity.Rare && c.Element == "generic").Name;
            var commons = cards.All.Where(c => c.Rarity == CardRarity.Common && c.Element == "generic" && !pool.InitialDeck.Any(e => e.CardId == c.Name)).Take(3).Select(c => c.Name).ToArray();
            var coordinator = Fixture(round, new[] { rare, commons[0], commons[1] });
            var before = coordinator.CurrentState.Players[Human].Draft.StudyPoints;
            Buy(coordinator, rare);
            Check(before - Player(coordinator).Draft.StudyPoints == (round is >= 4 and <= 6 ? 0 : 2), "Rare free window");
            before = Player(coordinator).Draft.StudyPoints;
            Buy(coordinator, commons[0]);
            Check(before - Player(coordinator).Draft.StudyPoints == (round <= 3 ? 0 : 1), "Common free window/shared free flag");
            before = Player(coordinator).Draft.StudyPoints; Buy(coordinator, commons[1]);
            Check(before - Player(coordinator).Draft.StudyPoints == 1, "Only one free purchase per round");
            var remove = Player(coordinator).Deck.Cards.Last();
            var result = coordinator.Submit(new RemoveCardCommand(coordinator.CurrentState.Id, Human, remove.InstanceId, Next(coordinator)));
            Check(result.Accepted == (round >= 4), "Removal round window");
            if (round >= 4)
            {
                var oldFree = coordinator.CurrentState.SharedCardInventory[remove.CardId];
                Check(coordinator.CurrentState.PendingPoolReturns.GetValueOrDefault(remove.CardId) == 1 && Player(coordinator).Draft.RemovalCount == 1, "Removal deferred return");
                before = Player(coordinator).Draft.StudyPoints;
                remove = Player(coordinator).Deck.Cards.Last();
                result = coordinator.Submit(new RemoveCardCommand(coordinator.CurrentState.Id, Human, remove.InstanceId, Next(coordinator)));
                Check(result.Accepted == (round >= 7), "Removal limit");
                if (round >= 7) Check(before - Player(coordinator).Draft.StudyPoints == 1, "Second removal costs one");
                Check(coordinator.CurrentState.SharedCardInventory[commons[1]] == oldFree, "Deleted copy returned too early");
            }
            // Next-round income, carry and win/loss rewards, independent of combat strength.
            foreach (var streak in new[] { 0, 2, 3, 5, 8 })
            foreach (var win in new[] { true, false })
            {
                var c = Fixture(round, Array.Empty<string>()); var state = c.CurrentState;
                var participants = state.Players.ToDictionary(p => p.Key, p => p.Value with { Draft = p.Value.Draft with { StudyPoints = 9, IsCompleted = true },
                    WinStreak = p.Key == Human && win ? streak : 0, LossStreak = p.Key == Human && !win ? streak : 0 });
                var pairings = new FirstRoundPairingService().CreateFirstRound(participants);
                var results = pairings.Select(p => new BattleResult(p.BattleId, p.PlayerA, p.PlayerB,
                    p.PlayerA == Human || p.PlayerB == Human ? (win ? Human : p.PlayerA == Human ? p.PlayerB : p.PlayerA) : p.PlayerA, 1, false)).ToArray();
                c = MatchCoordinator.Restore(cards, pool, state with { Phase = MatchPhase.Settlement, Players = participants, Pairings = pairings, BattleResults = results });
                Accept(c, new AdvanceSettlementCommand(state.Id, Human, Next(c)));
                var income = round + 1 <= 2 ? 2 : round + 1 <= 5 ? 3 : 4;
                Check(Player(c).Draft.StudyPoints == income + 2 + ((streak + 1) % 3 == 0 ? 1 : 0), "Income/carry/streak reward");
            }
        }
        var legendary = cards.All.First(c => c.Rarity == CardRarity.Legendary && c.Element == "generic").Name;
        var protectedMatch = Fixture(8, new[] { legendary }); Buy(protectedMatch, legendary);
        var ownedLegend = Player(protectedMatch).Deck.Cards.Last();
        Check(!protectedMatch.Submit(new RemoveCardCommand(protectedMatch.CurrentState.Id, Human, ownedLegend.InstanceId, Next(protectedMatch))).Accepted, "Legendary deletion protection");
        var route = cards.All.First(c => c.Kind == CardKind.RouteLegendary && c.Element == "fire");
        var stateBefore = protectedMatch.CurrentState;
        var pp = stateBefore.Players.ToDictionary(p => p.Key, p => p.Value);
        pp[Human] = pp[Human] with { Draft = pp[Human].Draft with { SpecializationElement = "fire" } };
        protectedMatch = MatchCoordinator.Restore(cards, pool, stateBefore with { Players = pp });
        Check(!protectedMatch.Submit(new ChooseRouteCommand(stateBefore.Id, Human, route.Name, Next(protectedMatch))).Accepted, "Route outside displayed offers");
        var fireNames = cards.All.Where(c => c.Element == "fire" && c.Rarity == CardRarity.Common && c.Layers > 0).Take(3).Select(c => c.Name).ToArray();
        var specialization = Fixture(8, fireNames);
        foreach (var name in fireNames) Buy(specialization, name);
        Check(Player(specialization).Draft.SpecializationElement == "fire" && Player(specialization).Deck.Cards.Count(c => cards.Get(c.CardId).Kind == CardKind.Specialization) == 1,
            "Three same-element cards must immediately grant exactly one specialization");
        Check(!specialization.Submit(new RemoveCardCommand(specialization.CurrentState.Id, Human,
            Player(specialization).Deck.Cards.First(c => c.CardId == fireNames[0]).InstanceId, Next(specialization))).Accepted, "Main-element minimum three");

        var allCommon = cards.All.Where(c => c.Rarity == CardRarity.Common && c.Element == "generic" && !pool.InitialDeck.Any(e => e.CardId == c.Name)).Take(8).Select(c => c.Name).ToArray();
        var allPurchased = Fixture(1, allCommon);
        foreach (var name in allCommon) Buy(allPurchased, name);
        var unchanged = StateHasher.Hash(allPurchased.CurrentState);
        Check(!allPurchased.Submit(new RefreshOffersCommand(allPurchased.CurrentState.Id, Human, Next(allPurchased))).Accepted && unchanged == StateHasher.Hash(allPurchased.CurrentState), "All purchased refresh must be rejected without charge");

        MatchCoordinator Fixture(int round, string[] names)
        {
            var c = new MatchCoordinator(cards, pool);
            var s = c.Start(new(new("economy-audit"), 42, new[] { new PlayerSetup(Human, PlayerKind.Human, "P"), new PlayerSetup(new("ai-1"), PlayerKind.Ai, "A"),
                new PlayerSetup(new("ai-2"), PlayerKind.Ai, "B"), new PlayerSetup(new("ai-3"), PlayerKind.Ai, "C") }, Round: round, InitialStudyPoints: 20,
                OffersPerPlayer: 8, AllowRefresh: true, AllowRemove: true, AllowSpecialization: true, AllowRouteSelection: true));
            var players = s.Players.ToDictionary(p => p.Key, p => p.Value);
            players[Human] = players[Human] with { Draft = players[Human].Draft with { Offers = names.Select((n, i) => new OfferSlot($"human:r{round}:offer:{i:D2}",
                new(new($"human:fixture:{i}"), n, Human), (int)cards.Get(n).Rarity + 1)).ToArray() } };
            return MatchCoordinator.Restore(cards, pool, s with { Phase = MatchPhase.Draft, Players = players });
        }
    }
    private static PlayerState Player(MatchCoordinator c) => c.CurrentState.Players[Human];
    private static CommandSequence Next(MatchCoordinator c) => new(c.CurrentState.EventSequence + 1);
    private static void Buy(MatchCoordinator c, string name) => Accept(c, new BuyCardCommand(c.CurrentState.Id, Human, Player(c).Draft.Offers.Single(o => o.Card.CardId == name).SlotId, Next(c)));
    private static void Accept(MatchCoordinator c, IGameCommand command) { var result = c.Submit(command); Check(result.Accepted, result.Rejection?.Code ?? "Rejected"); }
    private static void Check(bool condition, string message) { if (!condition) throw new InvalidDataException("Draft economy audit: " + message); }
}
