using Magicians.Core.Cards;
using Magicians.Core.Common;
using Magicians.Core.Match;

namespace Magicians.Core.Draft;

public sealed record OfferAllocation(IReadOnlyDictionary<PlayerId, IReadOnlyList<OfferSlot>> Offers,
    IReadOnlyDictionary<PlayerId, IReadOnlyList<string>> SeenNames, IReadOnlyList<string> Audit);

// Pure planning on caller-owned inventory/RNG copies. The coordinator commits the entire result.
// Joint min-cost flow: source -> slot -> player/name -> shared name -> sink.
// This allows a scarce card to be reassigned to another player instead of favouring the first seat.
public sealed class DraftOfferAllocator(CardDatabase cards, FrozenDraftRules rules)
{
    private static readonly string[] Elements = { "fire", "water", "earth", "wind", "poison" };
    private sealed record Slot(PlayerState Player, int Index, int Rank, string Element, string? Type, bool Guaranteed, bool RouteAllowed);
    public OfferAllocation Generate(IReadOnlyList<PlayerState> players, IReadOnlyDictionary<PlayerId, int[]> templates,
        int round, bool refresh, IDictionary<string, int> inventory, IDictionary<string, int> unseen,
        IDeterministicRandom random)
    {
        var slots = new List<Slot>();
        var audit = new List<string>();
        foreach (var p in players.OrderBy(p => p.Id.Value, StringComparer.Ordinal))
        {
            var ranks = templates[p.Id].ToArray();
            var purchased = refresh ? p.Draft.Offers.Where(o => o.IsPurchased).Select(o => Index(o.SlotId)).ToHashSet() : new HashSet<int>();
            var active = Enumerable.Range(0, ranks.Length).Where(i => !purchased.Contains(i)).ToArray();
            if (active.Length == 0) continue;
            int? upgraded = null;
            if (refresh && rules.IsPity(round))
            {
                var minimum = active.Min(i => ranks[i]);
                var lowest = active.Where(i => ranks[i] == minimum).ToArray();
                upgraded = lowest[random.NextInt(0, lowest.Length)];
                ranks[upgraded.Value] = 3;
                audit.Add($"{p.Id}:refresh-pity-slot={upgraded}");
            }
            var target = rules.EnchantmentTarget(p.Draft.SpecializationElement, active.Length, random);
            var allowed = p.Draft.SpecializationElement is { } main ? new List<string> { main } : Elements.ToList();
            if (refresh && p.Draft.SpecializationElement is null)
            {
                var bought = p.Draft.Offers.Where(o => o.IsPurchased).Select(o => cards.Get(o.Card.CardId).Element).ToHashSet();
                allowed.RemoveAll(e => bought.Contains(e) && FrozenDraftRules.Unit(random) >= rules.BoughtElementAdmission);
            }
            var used = new HashSet<string>();
            var limitedRoutes = round is 10 or 12 && p.Draft.RouteLegendaryId is not null;
            var routesSeen = p.Draft.ShownLegendaryIds.Count(n => cards.Get(n).Kind == CardKind.RouteLegendary);
            var routeSlot = limitedRoutes && routesSeen == 0
                ? active.Where(i => ranks[i] == 3).Select(i => (int?)i).FirstOrDefault() : null;
            if (limitedRoutes) audit.Add($"{p.Id}:route-cap=1;previously-shown={routesSeen};eligible-slot={routeSlot}");
            var assigned = new Dictionary<int, string>();
            var types = new Dictionary<int, string>();
            string Element()
            {
                var options = allowed.Where(e => p.Draft.SpecializationElement is not null || !used.Contains(e)).ToArray();
                if (options.Length == 0) return "generic";
                var element = options[random.NextInt(0, options.Length)]; used.Add(element); return element;
            }
            foreach (var i in active.Where(i => ranks[i] == 3))
            {
                var routeAllowed = !limitedRoutes || i == routeSlot;
                var type = !refresh && rules.IsPity(round) && i < 2 && routeAllowed ? "route" : rules.LegendaryType(round, random, routeAllowed);
                types[i] = type;
                assigned[i] = type is "route" or "stacking" ? Element() : "generic";
            }
            var rest = active.Where(i => !assigned.ContainsKey(i)).ToList(); random.Shuffle(rest);
            var need = Math.Max(0, target - assigned.Values.Count(e => e != "generic"));
            foreach (var i in rest) { assigned[i] = need > 0 ? Element() : "generic"; if (assigned[i] != "generic") need--; }
            foreach (var i in active) slots.Add(new(p, i, ranks[i], assigned[i], types.GetValueOrDefault(i),
                rules.IsPity(round) && (refresh ? i == upgraded : i < 3), !limitedRoutes || i == routeSlot));
            audit.Add($"{p.Id}:element-target={target}/{active.Length};allowed={string.Join(',', allowed)}");
        }
        if (!refresh && rules.IsPity(round)) BalanceGuaranteedRouteElements(slots, inventory, unseen, random, audit);
        var flow = new Flow(); var source = flow.Node("source"); var sink = flow.Node("sink");
        var available = inventory.Where(p => p.Value > 0).OrderBy(p => p.Key, StringComparer.Ordinal)
            .Select(p => (Card: cards.Get(p.Key), Count: cards.Get(p.Key).Rarity == CardRarity.Legendary ? Math.Min(p.Value, unseen.TryGetValue(p.Key, out var remaining) ? remaining : 0) : p.Value))
            .Where(p => p.Count > 0).ToArray();
        foreach (var c in available) flow.Edge(flow.Node("name:" + c.Card.Name), sink, c.Count, 0);
        var playerNames = new HashSet<string>();
        var choices = new Dictionary<Slot, List<(string Name, Flow.Arc Edge)>>();
        foreach (var s in slots)
        {
            var node = flow.Node($"slot:{s.Player.Id}:{s.Index}"); flow.Edge(source, node, 1, 0);
            var owned = s.Player.Deck.Cards.Select(c => c.CardId).ToHashSet(StringComparer.Ordinal);
            choices[s] = new();
            foreach (var (c, count) in available)
            {
                var rank = (int)c.Rarity;
                if (rank > s.Rank || owned.Contains(c.Name)) continue;
                // Keep this exclusion at the final flow edge as well as in the
                // candidate planner: no player may ever be offered a name they
                // already own, including after a refresh or pity upgrade.
                if (s.Player.Deck.Cards.Any(card => card.CardId == c.Name)) continue;
                if (c.Kind == CardKind.RouteLegendary && !s.RouteAllowed) continue;
                if (s.Player.Draft.SpecializationElement is { } main && c.Element != "generic" && c.Element != main) continue;
                if (s.Player.Draft.SpecializationElement is null && c.Element != "generic" && c.Element != s.Element) continue;
                if (c.Rarity == CardRarity.Legendary && s.Player.Draft.ShownLegendaryIds.Contains(c.Name)) continue;
                var key = $"pn:{s.Player.Id}:{c.Name}";
                var pn = flow.Node(key);
                if (playerNames.Add(key)) flow.Edge(pn, flow.Node("name:" + c.Name), 1, 0);
                long cost = (s.Rank - rank) * (s.Guaranteed ? 10_000_000L * (!refresh ? 4 - s.Index : 1) : 1_000_000L);
                if (c.Element != s.Element) cost += 10_000;
                if (rank == 3 && s.Type is not null && Type(c) != s.Type) cost += 50_000 * (!refresh && rules.IsPity(round) && s.Index < 2 ? 2 : 1);
                cost += (long)(100 * -Math.Log(FrozenDraftRules.Unit(random)) / count);
                choices[s].Add((c.Name, flow.Edge(node, pn, 1, cost)));
            }
            flow.Edge(node, sink, 1, 1_000_000_000L);
        }
        flow.Solve(source, sink, slots.Count);
        var offers = players.ToDictionary(p => p.Id, _ => new List<OfferSlot>());
        var seen = players.ToDictionary(p => p.Id, p => p.Draft.ShownLegendaryIds.ToList());
        foreach (var s in slots)
        {
            var name = choices[s].Where(c => c.Edge.Capacity == 0).Select(c => c.Name).SingleOrDefault();
            if (name is null) { audit.Add($"{s.Player.Id}:slot={s.Index}:empty:requested={s.Rank}"); continue; }
            var c = cards.Get(name); inventory[name]--;
            if (c.Rarity == CardRarity.Legendary) { unseen[name]--; seen[s.Player.Id].Add(name); }
            if ((int)c.Rarity != s.Rank || c.Element != s.Element || s.Type is not null && Type(c) != s.Type)
                audit.Add($"{s.Player.Id}:slot={s.Index}:requested={s.Rank}/{s.Element}/{s.Type}:actual={c.Rarity}/{c.Element}/{Type(c)}");
            var slotId = $"{s.Player.Id.Value}:r{round}:offer:{s.Index:D2}";
            var instance = refresh ? $"{s.Player.Id.Value}:offer:r{round}:refresh:{slotId}" : round == 1 ? $"{s.Player.Id.Value}:offer:{s.Index:D2}" : $"{s.Player.Id.Value}:offer:r{round}:{s.Index:D2}";
            offers[s.Player.Id].Add(new(slotId, new(new(instance), name, s.Player.Id), (int)c.Rarity + 1));
        }
        return new(offers.ToDictionary(p => p.Key, p => (IReadOnlyList<OfferSlot>)p.Value.ToArray()),
            seen.ToDictionary(p => p.Key, p => (IReadOnlyList<string>)p.Value.ToArray()), audit.ToArray());
    }
    public static int Index(string slotId) => int.Parse(slotId[(slotId.LastIndexOf(':') + 1)..]);
    private string Type(CardDefinition c) => c.Kind == CardKind.RouteLegendary ? "route" : c.Element != "generic" ? "stacking" : rules.IsEngine(c.Name) ? "generic_engine" : "generic_other";

    private void BalanceGuaranteedRouteElements(List<Slot> slots, IDictionary<string, int> inventory,
        IDictionary<string, int> unseen, IDeterministicRandom random, List<string> audit)
    {
        // Element sampling is uniform before feasibility constraints. Reassign only when
        // necessary to avoid artificial shortages caused by four seats picking one element.
        // Route copies are unique, so free counts by element exactly describe route capacity.
        var targets = slots.Where(s => s.Index < 2 && s.Guaranteed && s.Type == "route").ToArray();
        var flow = new Flow(); var source = flow.Node("source"); var sink = flow.Node("sink");
        foreach (var element in Elements)
        {
            var count = inventory.Where(p => p.Value > 0 && cards.Get(p.Key).Kind == CardKind.RouteLegendary && cards.Get(p.Key).Element == element)
                .Sum(p => Math.Min(p.Value, unseen.TryGetValue(p.Key, out var left) ? left : 0));
            flow.Edge(flow.Node("element:" + element), sink, count, 0);
        }
        var buckets = new HashSet<string>();
        var choices = new Dictionary<Slot, List<(string Element, Flow.Arc Edge)>>();
        foreach (var slot in targets)
        {
            var node = flow.Node($"slot:{slot.Player.Id}:{slot.Index}"); flow.Edge(source, node, 1, 0);
            var options = slot.Player.Draft.SpecializationElement is { } main ? new[] { main } : Elements;
            choices[slot] = new();
            foreach (var element in options)
            {
                var key = $"pe:{slot.Player.Id}:{element}";
                var enter = flow.Node(key + ":in"); var exit = flow.Node(key + ":out");
                if (buckets.Add(key))
                {
                    flow.Edge(enter, exit, slot.Player.Draft.SpecializationElement is null ? 1 : 2, 0);
                    flow.Edge(exit, flow.Node("element:" + element), 2, 0);
                }
                choices[slot].Add((element, flow.Edge(node, enter, 1, element == slot.Element ? 0 : 1000 + random.NextInt(0, 100))));
            }
            flow.Edge(node, sink, 1, 1_000_000_000);
        }
        flow.Solve(source, sink, targets.Length);
        foreach (var group in slots.GroupBy(s => s.Player.Id).ToArray())
        {
            if (group.First().Player.Draft.SpecializationElement is not null) continue;
            var used = new HashSet<string>(); var assigned = new Dictionary<int, string>();
            foreach (var slot in group.Where(choices.ContainsKey))
            {
                var selected = choices[slot].Where(c => c.Edge.Capacity == 0).Select(c => c.Element).SingleOrDefault();
                if (selected is null) { audit.Add($"{group.Key}:route-target-shortage:slot={slot.Index}"); continue; }
                assigned[slot.Index] = selected; used.Add(selected);
                if (selected != slot.Element) audit.Add($"{group.Key}:route-element-rebalanced:slot={slot.Index}:{slot.Element}->{selected}");
            }
            foreach (var slot in group.Where(s => !assigned.ContainsKey(s.Index)))
            {
                var element = slot.Element;
                if (element != "generic" && !used.Add(element))
                {
                    var options = Elements.Where(e => !used.Contains(e)).ToArray();
                    element = options.Length > 0 ? options[random.NextInt(0, options.Length)] : "generic";
                    if (element != "generic") used.Add(element);
                }
                assigned[slot.Index] = element;
            }
            foreach (var slot in group) slots[slots.IndexOf(slot)] = slot with { Element = assigned[slot.Index] };
        }
    }

    private sealed class Flow
    {
        public sealed class Arc(int to, int reverse, int capacity, long cost)
        { public int To = to; public int Reverse = reverse; public int Capacity = capacity; public long Cost = cost; }
        private readonly Dictionary<string, int> _nodes = new(StringComparer.Ordinal);
        private readonly List<List<Arc>> _graph = new();
        public int Node(string name) { if (_nodes.TryGetValue(name, out var n)) return n; n = _graph.Count; _graph.Add(new()); _nodes[name] = n; return n; }
        public Arc Edge(int from, int to, int capacity, long cost)
        {
            var arc = new Arc(to, _graph[to].Count, capacity, cost);
            _graph[to].Add(new(from, _graph[from].Count, 0, -cost)); _graph[from].Add(arc); return arc;
        }
        public void Solve(int source, int sink, int units)
        {
            for (var unit = 0; unit < units; unit++)
            {
                var distance = Enumerable.Repeat(long.MaxValue, _graph.Count).ToArray();
                var parent = new (int Node, int Edge)[_graph.Count]; var queued = new bool[_graph.Count];
                var queue = new Queue<int>(); queue.Enqueue(source); queued[source] = true; distance[source] = 0;
                while (queue.TryDequeue(out var from))
                {
                    queued[from] = false;
                    for (var i = 0; i < _graph[from].Count; i++)
                    {
                        var edge = _graph[from][i];
                        if (edge.Capacity <= 0 || distance[edge.To] <= distance[from] + edge.Cost) continue;
                        distance[edge.To] = distance[from] + edge.Cost; parent[edge.To] = (from, i);
                        if (!queued[edge.To]) { queue.Enqueue(edge.To); queued[edge.To] = true; }
                    }
                }
                if (distance[sink] == long.MaxValue) throw new InvalidOperationException("No legal draft allocation path.");
                for (var n = sink; n != source;)
                {
                    var p = parent[n]; var edge = _graph[p.Node][p.Edge]; edge.Capacity--; _graph[n][edge.Reverse].Capacity++; n = p.Node;
                }
            }
        }
    }
}
