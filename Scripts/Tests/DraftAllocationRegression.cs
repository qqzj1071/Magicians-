using System.Text.Json;
using Magicians.Application;
using Magicians.Core.AI;
using Magicians.Core.Cards;
using Magicians.Core.Common;
using Magicians.Core.Draft;
using Magicians.Core.Match;

namespace Magicians.Tests;

public static class DraftAllocationRegression
{
    public static void Run(CardDatabase cards, Slice1CardPool pool, string root)
    {
        var rules = pool.DraftRules!;
        var report = new List<object>();
        // These caps bound the probability of >=1 hit; they do not cap the card count in one face.
        double Hit(int round, int rank, bool both) => 1 - Math.Pow(1 - rules.Weights(round, 0)[rank], 8) *
            (both ? Math.Pow(1 - rules.Weights(round, 1)[rank], 8) : 1);
        Check(Hit(2, 2, false) <= .2 && Hit(2, 2, true) <= .5 && Hit(6, 3, true) <= .1 && Hit(7, 3, true) <= .2, "Probability hard caps");
        for (var round = 1; round <= 20; round++)
        for (var seed = 0; seed < 12; seed++)
        {
            var coordinator = Start(cards, pool, round, seed);
            var state = coordinator.CurrentState;
            Accept(coordinator, new BeginDraftCommand(state.Id, new("human"), new(state.EventSequence + 1)));
            state = coordinator.CurrentState;
            var first = state;
            VerifyInventory(state, pool);
            var seen = new Dictionary<string, int>();
            foreach (var p in state.Players.Values)
            {
                Check(p.Draft.FirstRarities.Count == 8 && p.Draft.RefreshRarities.Count == 8, "Both templates pre-rolled");
                Face(p, p.Draft.FirstRarities, false);
                foreach (var o in p.Draft.Offers.Where(o => cards.Get(o.Card.CardId).Rarity == CardRarity.Legendary))
                    seen[o.Card.CardId] = seen.GetValueOrDefault(o.Card.CardId) + 1;
                if (rules.IsPity(round))
                {
                    Check(p.Draft.Offers.Where(o => DraftOfferAllocator.Index(o.SlotId) < 3).Count(o => cards.Get(o.Card.CardId).Rarity == CardRarity.Legendary) == 3, "Three legendary pity slots");
                    Check(p.Draft.Offers.Count(o => cards.Get(o.Card.CardId).Kind == CardKind.RouteLegendary) >= 2, "Avoidable first-face route shortage");
                }
            }
            foreach (var p in first.Players.Values)
            {
                // Buy an actual displayed card before refreshing; unchanged purchased positions are essential.
                var action = AiObservations.Draft(coordinator.CurrentState, p.Id, cards).LegalActions.First(a => a.Kind == "buy");
                Accept(coordinator, new BuyCardCommand(state.Id, p.Id, action.Slot!, new(coordinator.CurrentState.EventSequence + 1)));
                var bought = coordinator.CurrentState.Players[p.Id].Draft.Offers.Single(o => o.IsPurchased);
                var freeUsed = coordinator.CurrentState.Players[p.Id].Draft.FreePurchaseUsed;
                var beforeRepeat = StateHasher.Hash(coordinator.CurrentState);
                var duplicate = coordinator.Submit(new BuyCardCommand(state.Id, p.Id, bought.SlotId, new(coordinator.CurrentState.EventSequence + 1)));
                Check(!duplicate.Accepted && StateHasher.Hash(coordinator.CurrentState) == beforeRepeat, "Rapid duplicate buy cannot double-spend");
                Accept(coordinator, new RefreshOffersCommand(state.Id, p.Id, new(coordinator.CurrentState.EventSequence + 1)));
                var updated = coordinator.CurrentState.Players[p.Id];
                Check(updated.Draft.Offers.Single(o => o.IsPurchased) == bought, "Purchased position not refilled/compacted");
                Check(updated.Draft.RefreshRarities.SequenceEqual(p.Draft.RefreshRarities), "Refresh template immutable");
                Check(updated.Draft.FreePurchaseUsed == freeUsed, "Refresh reset free-purchase eligibility");
                Face(updated, updated.Draft.RefreshRarities, true);
                var previous = p.Draft.Offers.Where(o => cards.Get(o.Card.CardId).Rarity == CardRarity.Legendary).Select(o => o.Card.CardId).ToHashSet();
                foreach (var o in updated.Draft.Offers.Where(o => !o.IsPurchased && cards.Get(o.Card.CardId).Rarity == CardRarity.Legendary))
                { Check(!previous.Contains(o.Card.CardId), "Per-player legendary name repeated"); seen[o.Card.CardId] = seen.GetValueOrDefault(o.Card.CardId) + 1; }
                if (rules.IsPity(round))
                {
                    var active = Enumerable.Range(0, 8).Where(i => i != DraftOfferAllocator.Index(bought.SlotId)).ToArray();
                    var min = active.Min(i => p.Draft.RefreshRarities[i]);
                    var entry = updated.Draft.AllocationAudit.Single(a => a.Contains(":refresh-pity-slot="));
                    var index = int.Parse(entry[(entry.LastIndexOf('=') + 1)..]);
                    Check(active.Contains(index) && p.Draft.RefreshRarities[index] == min, "Refresh pity upgrades lowest active slot");
                }
                var hash = StateHasher.Hash(coordinator.CurrentState);
                var reject = coordinator.Submit(new RefreshOffersCommand(state.Id, p.Id, new(coordinator.CurrentState.EventSequence + 1)));
                Check(!reject.Accepted && StateHasher.Hash(coordinator.CurrentState) == hash, "Repeated refresh must be atomic rejection");
            }
            foreach (var name in seen.Keys) Check(seen[name] <= pool.OfferPool.Single(e => e.CardId == name).Count, "Physical legendary displayed twice");
            Check(coordinator.CurrentState.SharedCardInventory.Values.All(q => q >= 0), "Inventory nonnegative");
            VerifyInventory(coordinator.CurrentState, pool);
            // Restoration includes hidden templates, seen budgets and RNG state.
            var replay = MatchCoordinator.Restore(cards, pool, first);
            foreach (var p in first.Players.Values)
            {
                var action = AiObservations.Draft(replay.CurrentState, p.Id, cards).LegalActions.First(a => a.Kind == "buy");
                Accept(replay, new BuyCardCommand(state.Id, p.Id, action.Slot!, new(replay.CurrentState.EventSequence + 1)));
                Accept(replay, new RefreshOffersCommand(state.Id, p.Id, new(replay.CurrentState.EventSequence + 1)));
            }
            Check(StateHasher.Hash(replay.CurrentState) == StateHasher.Hash(coordinator.CurrentState), "Restore/replay mismatch");
            report.Add(new { Round = round, Seed = seed, Hash = StateHasher.Hash(coordinator.CurrentState),
                Deficits = coordinator.CurrentState.Players.Values.SelectMany(p => p.Draft.AllocationAudit).Where(a => a.Contains(":actual=") || a.Contains(":empty:")).ToArray() });
        }
        Scarcity(cards, pool);
        SpecializationAndAdmission(cards, pool);
        DraftEconomyRegression.Run(cards, pool);
        Display(root);
        var path = Path.GetFullPath(Path.Combine(root, "..", "runtime", "draft-rules-audit.json"));
        File.WriteAllText(path, JsonSerializer.Serialize(new { Status = "passed", Cases = report.Count, Caps = new {
            Round2FirstEpic = Hit(2, 2, false), Round2BothEpic = Hit(2, 2, true), Round6BothLegend = Hit(6, 3, true), Round7BothLegend = Hit(7, 3, true) }, Runs = report }, new JsonSerializerOptions { WriteIndented = true }));

        void Face(PlayerState p, IReadOnlyList<int> template, bool refresh)
        {
            var active = p.Draft.Offers.Where(o => !refresh || !o.IsPurchased).ToArray();
            Check(active.Select(o => o.Card.CardId).Distinct().Count() == active.Length, "Face duplicate names");
            var elements = active.Select(o => cards.Get(o.Card.CardId).Element).Where(e => e != "generic").ToArray();
            if (p.Draft.SpecializationElement is null) Check(elements.Distinct().Count() == elements.Length, "Pre-specialization duplicate element");
            foreach (var o in active)
            {
                var c = cards.Get(o.Card.CardId); var i = DraftOfferAllocator.Index(o.SlotId);
                Check((int)c.Rarity <= template[i] || refresh && rules.IsPity(p.Draft.Round) && c.Rarity == CardRarity.Legendary, "Illegal rarity upgrade");
                Check(p.Draft.Round >= 6 || c.Rarity != CardRarity.Legendary, "Legend before round 6");
                Check(p.Draft.Round != 1 || c.Rarity <= CardRarity.Rare, "Epic in round 1");
                Check(!p.Deck.Cards.Any(c => c.CardId == o.Card.CardId), "Owned name offered");
            }
        }
    }
    private static MatchCoordinator Start(CardDatabase cards, Slice1CardPool pool, int round, int seed)
    {
        var c = new MatchCoordinator(cards, pool);
        c.Start(new(new("allocation-audit"), seed, new[] { new PlayerSetup(new("human"), PlayerKind.Human, "P"),
            new PlayerSetup(new("ai-1"), PlayerKind.Ai, "A"), new PlayerSetup(new("ai-2"), PlayerKind.Ai, "B"), new PlayerSetup(new("ai-3"), PlayerKind.Ai, "C") },
            Round: round, InitialStudyPoints: 100, OffersPerPlayer: 8, AllowRefresh: true, AllowRemove: true, AllowSpecialization: true, AllowRouteSelection: true)); return c;
    }
    private static void Scarcity(CardDatabase cards, Slice1CardPool pool)
    {
        var c = Start(cards, pool, 1, 42); var players = c.CurrentState.Players.Values.Take(2).ToArray();
        var owned = players[0].Deck.Cards.Select(c => c.CardId).ToHashSet();
        var names = cards.All.Where(c => c.Element == "generic" && c.Rarity == CardRarity.Common && !owned.Contains(c.Name)).Take(2).Select(c => c.Name).ToArray();
        players[1] = players[1] with { Deck = players[1].Deck with { Cards = players[1].Deck.Cards.Append(new(new("owned-test"), names[0], players[1].Id)).ToArray() } };
        var stock = names.ToDictionary(n => n, _ => 1); var unseen = new Dictionary<string, int>();
        var allocation = new DraftOfferAllocator(cards, pool.DraftRules!).Generate(players, players.ToDictionary(p => p.Id, _ => new[] { 2 }), 1, false, stock, unseen, new SeededRandom(4));
        Check(allocation.Offers[players[0].Id].Single().Card.CardId == names[0] && allocation.Offers[players[1].Id].Single().Card.CardId == names[1], "Joint solver failed scarce-card reassignment");
        Check(allocation.Audit.Count(a => a.Contains(":actual=")) == 2, "Shortage downgrade not logged");
        var empty = new DraftOfferAllocator(cards, pool.DraftRules!).Generate(players, players.ToDictionary(p => p.Id, _ => new[] { 0 }), 1, false, stock, unseen, new SeededRandom(4));
        Check(empty.Offers.Values.All(o => o.Count == 0) && empty.Audit.Count(a => a.Contains(":empty:")) == 2, "Empty inventory must not invent copies");
    }
    private sealed class FixedRandom(int value) : IDeterministicRandom
    { public ulong State => 1; public int NextInt(int minInclusive, int maxExclusive) => minInclusive + value % (maxExclusive - minInclusive); public void Shuffle<T>(IList<T> items) { } }
    private static void SpecializationAndAdmission(CardDatabase cards, Slice1CardPool pool)
    {
        var p = Start(cards, pool, 8, 1).CurrentState.Players.Values.First();
        var stock = pool.OfferPool.ToDictionary(e => e.CardId, e => e.Count);
        var fire = cards.All.First(c => c.Element == "fire" && c.Rarity == CardRarity.Common);
        p = p with { Draft = p.Draft with { Offers = new[] { new OfferSlot($"{p.Id}:r8:offer:00", new(new("bought-fire"), fire.Name, p.Id), 1, true) } } };
        foreach (var spec in new string?[] { null, "water" })
        {
            var player = p with { Draft = p.Draft with { SpecializationElement = spec } };
            var inventory = stock.ToDictionary(e => e.Key, e => e.Value);
            var unseen = inventory.Where(e => cards.Get(e.Key).Rarity == CardRarity.Legendary).ToDictionary(e => e.Key, e => e.Value);
            var result = new DraftOfferAllocator(cards, pool.DraftRules!).Generate(new[] { player }, new Dictionary<PlayerId, int[]> { [p.Id] = new int[8] }, 8, true, inventory, unseen, new FixedRandom(500_000_000));
            Check(result.Offers[p.Id].All(o => cards.Get(o.Card.CardId).Element is "generic" || cards.Get(o.Card.CardId).Element == (spec ?? cards.Get(o.Card.CardId).Element) && cards.Get(o.Card.CardId).Element != "fire"), "Foreign/bought element restriction");
        }
    }
    private static void Display(string root)
    {
        var path = Path.GetFullPath(Path.Combine(root, "..", "runtime", "display-settings-test.cfg"));
        Check(new DisplayPreferences().Width == 1920 && new DisplayPreferences().Height == 1080, "Display default");
        var custom = new DisplayPreferences(2560, 1440, true); Check(custom.Save(path) == Godot.Error.Ok && DisplayPreferences.Load(path) == custom, "Display persistence");
        Check(new DisplayPreferences(-1, 0).Validated() == new DisplayPreferences(), "Invalid display fallback");
        Check(DisplayPreferences.Load(path + ".absent") == new DisplayPreferences(), "First launch default");
    }
    public static void VerifyInventory(MatchState state, Slice1CardPool pool)
    {
        var owned = state.Players.Values.Where(p => p.Kind != PlayerKind.Ghost).SelectMany(p => p.Deck.Cards)
            .Where(c => !c.InstanceId.Value.Contains(":initial:") && !c.InstanceId.Value.Contains(":specialization:"))
            .GroupBy(c => c.CardId).ToDictionary(g => g.Key, g => g.Count());
        var reserved = state.Players.Values.Where(p => p.Kind != PlayerKind.Ghost).SelectMany(p => p.Draft.Offers.Where(o => !o.IsResolved))
            .GroupBy(o => o.Card.CardId).ToDictionary(g => g.Key, g => g.Count());
        foreach (var entry in pool.OfferPool)
            Check(state.SharedCardInventory[entry.CardId] + owned.GetValueOrDefault(entry.CardId) +
                reserved.GetValueOrDefault(entry.CardId) + state.PendingPoolReturns.GetValueOrDefault(entry.CardId) == entry.Count,
                "Inventory conservation: " + entry.CardId);
    }
    private static void Accept(MatchCoordinator c, IGameCommand command) { var r = c.Submit(command); Check(r.Accepted, r.Rejection?.Code ?? "rejected"); }
    private static void Check(bool condition, string message) { if (!condition) throw new InvalidDataException("Draft audit: " + message); }
}
