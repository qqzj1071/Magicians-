using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Magicians.Core.Cards;
using Magicians.Core.Combat;
using Magicians.Core.Common;
using Magicians.Core.Match;

namespace Magicians.Core.AI;

public sealed record PublicAiPlayer(string Id, string Spec, string Route, int Life, bool Ghost);
public sealed record AiOwnedCard(string Id, string Name);
public sealed record AiOffer(string Slot, string Name, int Cost, bool FreeEligible);
public sealed record AiLegalDraftAction(string Kind, string? Slot = null, string? Card = null, string? Replace = null, int Cost = 0);
public sealed record AiDraftView(string Player, int Round, int Points, bool FreeUsed, int Refreshes, int Removals,
    int WinStreak, int LossStreak, string Spec, string Route, IReadOnlyList<AiOwnedCard> Deck,
    IReadOnlyList<AiOffer> Offers, IReadOnlyList<PublicAiPlayer> PublicPlayers, string NextOpponent,
    IReadOnlyList<AiLegalDraftAction> LegalActions)
{
    public int LossEstimate { get; init; }
}
public sealed record AiCombatView(string Player, int Round, int ActionValue,
    IReadOnlyDictionary<string, object?> Self, IReadOnlyDictionary<string, object?> Opponent,
    IReadOnlyList<AiOwnedCard> Hand, IReadOnlyList<string> OwnDeck, IReadOnlyList<string> OwnDiscard,
    IReadOnlyList<string> OwnPlayed, string OwnSpec, string OwnRoute, string OpponentSpec, string OpponentRoute);

/// <summary>The only authority-to-policy boundary. No full state objects, RNG, draw
/// order, hidden inventory, pending enemy actions or future offers cross it.</summary>
public static class AiObservations
{
    public static readonly JsonSerializerOptions Json = new() { PropertyNamingPolicy = JsonNamingPolicy.CamelCase };
    private static readonly string[] VisibleResources =
    {
        "Life", "Shield", "Attack", "Defense", "Energy", "EarthLayers", "WaterLayers", "WindLayers", "FireLayers",
        "PoisonEnchantmentLayers", "PoisonLayers", "Embers", "Tides", "EmberDamageActive", "TideActive", "EarthBarrierActive",
        "WindGaleActive", "PlagueActive", "EmberCoreActive", "AshCycleActive", "BastionHeartActive", "WindTraceActive",
        "WindArrowActive", "WindChaseActive", "BloodTideActive", "PlagueLifeDamageActive", "PoisonExplosionActive",
        "AttackIntervalModifier", "PermanentIntervalMultiplierPercent", "TemporaryIntervalMultiplierPercent",
        "NextDrawBonus", "NextEnergyBonus", "NextGapAdjustment", "PendingSubmissiles", "PendingWindSubmissiles",
        "NextWindSubmissileFlat", "NextWindSubmissileAttackPercent", "NextMissileBonusPercent", "NextMissileBonusFlat",
        "NextShieldPenetrationPercent", "NextDefensePenetrationPercent", "MainShieldPenetrationUntilDrawPercent",
        "MainDefensePenetrationPercent", "BattleAttackReduction", "BattleDefenseReduction", "TemporaryAttackReduction",
        "TemporaryDefenseReduction", "NegativeSuppressedUntilActionValue", "HealingReductionPercent", "HealingReductionUntilActionValue",
        "NextIncomingDamageMultiplierPercent", "NextIncomingDamageFlat", "BattleIncomingDamageMultiplierPercent",
        "BattleIncomingDamageUntilActionValue", "TemporaryShield", "NextMainTemporaryShieldPercent", "MainDamageBonusUntilDrawPercent",
        "NextPoisonOnHitLayers", "NextPoisonOnHitCharges", "ExtraPoisonTickCharges", "PoisonDecayIntervalPercent",
        "PoisonDecayProtectionCharges", "PoisonDecayKeepLast", "NextPoisonDecayActionValue", "WindTraceLayers",
        "WindTraceBonusLayers", "WindMainShotCount", "LastMainMissileActionValue", "LastMainMissileActualDamage",
        "ShieldBreakReturnPercent", "ShieldBreakReturnFlat", "ShieldBrokenThisBattle", "GuardianBarrierActive", "WarGodEmblemActive",
        "ActualHealingThisBattle", "NextMissileHealingPercent", "UnredeemedEmbersSpent", "AshRebirthUsed", "ShuffleCount", "TemperBonusUses"
    };

    public static IReadOnlyList<PublicAiPlayer> PublicPlayers(MatchState state) => state.Players.Values
        .OrderBy(p => p.Id.Value, StringComparer.Ordinal).Select(p => new PublicAiPlayer(p.Id.Value,
            p.Draft.SpecializationElement ?? "", p.Draft.RouteLegendaryId ?? "", p.TournamentLife, p.Kind == PlayerKind.Ghost)).ToArray();

    private static IReadOnlyDictionary<string, object?> Resources(CombatantState actor, int time, string route, IReadOnlyList<CardInstance> knownCards)
    {
        var resources = CombatResourceState.From(actor);
        var visible = VisibleResources.ToDictionary(name => name, name => typeof(CombatResourceState).GetProperty(name)!.GetValue(resources), StringComparer.Ordinal);
        visible["NextFire"] = actor.NextFire;
        visible["ShieldDecayActive"] = actor.ShieldDecay.Active;
        visible["ShieldDecayDamage"] = actor.ShieldDecay.PendingDamage;
        visible["ShieldDecayBonus"] = actor.ShieldDecay.NextBonusPercent;
        visible["ObservationTime"] = time;
        visible["RouteActivated"] = !string.IsNullOrEmpty(route) && knownCards.Any(c => c.CardId == route && actor.FirstPlayed.Contains(c.InstanceId));
        return visible;
    }

    public static AiCombatView Combat(MatchState match, BattleInstance instance, PlayerId player)
    {
        var self = instance.State.A.Player == player ? instance.State.A : instance.State.B;
        var enemy = instance.State.A.Player == player ? instance.State.B : instance.State.A;
        if (self.Player != player) throw new ArgumentException("Player is not in battle.");
        var own = match.Players[player];
        var opponent = match.Players[enemy.Player];
        var snapshot = self.Player == instance.Pairing.PlayerA ? instance.SnapshotA : instance.SnapshotB;
        var enemySnapshot = enemy.Player == instance.Pairing.PlayerA ? instance.SnapshotA : instance.SnapshotB;
        return new(player.Value, match.Round, instance.State.ActionValue,
            Resources(self, instance.State.ActionValue, own.Draft.RouteLegendaryId ?? "", snapshot.Cards),
            Resources(enemy, instance.State.ActionValue, opponent.Draft.RouteLegendaryId ?? "", enemySnapshot.Cards),
            self.CurrentPool.Select(c => new AiOwnedCard(c.InstanceId.Value, c.CardId)).ToArray(),
            snapshot.Cards.Select(c => c.CardId).OrderBy(n => n, StringComparer.Ordinal).ToArray(),
            self.DiscardPile.Select(c => c.CardId).OrderBy(n => n, StringComparer.Ordinal).ToArray(),
            snapshot.Cards.Where(c => self.FirstPlayed.Contains(c.InstanceId)).Select(c => c.CardId).OrderBy(n => n, StringComparer.Ordinal).ToArray(),
            own.Draft.SpecializationElement ?? "", own.Draft.RouteLegendaryId ?? "",
            opponent.Draft.SpecializationElement ?? "", opponent.Draft.RouteLegendaryId ?? "");
    }

    public static AiDraftView Draft(MatchState state, PlayerId player, CardDatabase cards)
    {
        var own = state.Players[player];
        var actions = new List<AiLegalDraftAction>();
        var offers = new List<AiOffer>();
        foreach (var offer in own.Draft.Offers.Where(o => !o.IsResolved))
        {
            var card = cards.Get(offer.Card.CardId);
            var free = !own.Draft.FreePurchaseUsed && ((state.Round <= 3 && card.Rarity == CardRarity.Common) ||
                (state.Round is >= 4 and <= 6 && card.Rarity is CardRarity.Common or CardRarity.Rare));
            var cost = free ? 0 : offer.Cost;
            offers.Add(new(offer.SlotId, card.Name, offer.Cost, free));
            if (own.Deck.Cards.Any(c => c.CardId == card.Name) ||
                own.Draft.SpecializationElement is { } element && card.Element != "generic" && card.Element != element) continue;
            var route = own.Deck.Cards.FirstOrDefault(c => cards.Get(c.CardId).Kind == CardKind.RouteLegendary);
            var legends = own.Deck.Cards.Where(c => cards.Get(c.CardId).Rarity == CardRarity.Legendary).ToArray();
            if (card.Kind == CardKind.RouteLegendary && route is not null)
            {
                if (own.Draft.SpecializationElement == card.Element && own.Draft.StudyPoints >= 2)
                    actions.Add(new("buy", offer.SlotId, card.Name, route.InstanceId.Value, 2));
            }
            else if (card.Rarity == CardRarity.Legendary && legends.Length >= 3)
            {
                foreach (var old in legends.Where(c => cards.Get(c.CardId).Kind != CardKind.RouteLegendary))
                {
                    if (own.Draft.SpecializationElement is { } main && own.Deck.Cards.Count(c => c.InstanceId != old.InstanceId && cards.Get(c.CardId).Element == main && cards.Get(c.CardId).Kind != CardKind.Specialization && cards.Get(c.CardId).Layers > 0) + (card.Element == main && card.Layers > 0 ? 1 : 0) < 3) continue;
                    if (cost <= own.Draft.StudyPoints) actions.Add(new("buy", offer.SlotId, card.Name, old.InstanceId.Value, cost));
                }
            }
            else if (cost <= own.Draft.StudyPoints) actions.Add(new("buy", offer.SlotId, card.Name, Cost: cost));
        }
        if (state.AllowRefresh && own.Draft.RefreshesUsed == 0 && own.Draft.StudyPoints >= 1 && own.Draft.Offers.Count(o => o.IsPurchased) < state.OffersPerPlayer)
            actions.Add(new("refresh", Cost: 1));
        var limit = state.Round <= 3 ? 0 : state.Round <= 6 ? 1 : 2;
        var removalCost = own.Draft.RemovalCount == 0 ? 0 : 1;
        if (state.AllowRemove && own.Draft.RemovalCount < limit && own.Deck.Cards.Count > 8 && removalCost <= own.Draft.StudyPoints)
            foreach (var card in own.Deck.Cards)
            {
                var definition = cards.Get(card.CardId);
                if (definition.Rarity is CardRarity.Legendary or CardRarity.Specialization) continue;
                if (own.Draft.SpecializationElement is { } main && definition.Element == main &&
                    own.Deck.Cards.Count(c => cards.Get(c.CardId).Element == main && cards.Get(c.CardId).Kind != CardKind.Specialization && cards.Get(c.CardId).Layers > 0) <= 3) continue;
                actions.Add(new("remove", Card: card.InstanceId.Value, Cost: removalCost));
            }
        actions.Add(new("finish"));
        var pairing = state.Pairings.FirstOrDefault(p => p.PlayerA == player || p.PlayerB == player);
        var next = pairing is null ? "" : (pairing.PlayerA == player ? pairing.PlayerB : pairing.PlayerA).Value;
        return new(player.Value, state.Round, own.Draft.StudyPoints, own.Draft.FreePurchaseUsed, own.Draft.RefreshesUsed,
            own.Draft.RemovalCount, own.WinStreak, own.LossStreak, own.Draft.SpecializationElement ?? "", own.Draft.RouteLegendaryId ?? "",
            own.Deck.Cards.Select(c => new AiOwnedCard(c.InstanceId.Value, c.CardId)).ToArray(), offers, PublicPlayers(state), next, actions)
            { LossEstimate = new FrozenV1TournamentDamageCalculator().CalculateLoss(state.Round, 500) };
    }

    public static string Hash(object observation) => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(
        JsonSerializer.Serialize(observation, Json)))).ToLowerInvariant();
}
