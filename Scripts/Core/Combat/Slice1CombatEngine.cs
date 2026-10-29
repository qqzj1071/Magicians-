using Magicians.Core.Cards;
using Magicians.Core.Common;

namespace Magicians.Core.Combat;

/// <summary>Pure C# battle executor. Submit one action per side per synchronized step.</summary>
public sealed class Slice1CombatEngine : ICombatEngine
{
    private readonly CardDatabase _cards;
    private readonly CardEffectRegistry _effects;
    private readonly EffectPipeline _pipeline;
    private readonly ICombatResolutionPolicy _resolutionPolicy;
    public Slice1CombatEngine(CardDatabase cards, CardEffectRegistry? effects = null, ICombatResolutionPolicy? resolutionPolicy = null)
    {
        _cards = cards;
        _effects = effects ?? CardEffectRegistry.CreateSlice1(cards);
        _pipeline = EffectPipelineDefaults.Create(cards, _effects);
        _resolutionPolicy = resolutionPolicy ?? new SnapshotCombatResolutionPolicy();
    }

    public CombatState Start(CombatSetup setup)
    {
        if (setup.A.Player == setup.B.Player || string.IsNullOrWhiteSpace(setup.Battle.Value))
            throw new ArgumentException("Battle requires an ID and two different players.");
        var all = setup.A.Cards.Concat(setup.B.Cards).ToArray();
        if (all.Select(c => c.InstanceId).Distinct().Count() != all.Length)
            throw new ArgumentException("Card instance IDs must be unique across both decks.");
        return new(setup.Battle, 0, 0, CombatPhase.Decision,
            Draw(Create(setup.A)), Draw(Create(setup.B)),
            Array.Empty<PendingAction>(), Array.Empty<PlayerId>(), null, false);
    }

    private CombatantState Create(CombatantSetup setup)
    {
        if (setup.Cards.Count == 0 || setup.Cards.Any(c => c.Owner != setup.Player))
            throw new ArgumentException("Each participant must own a nonempty deck.");
        foreach (var card in setup.Cards)
        {
            _cards.Get(card.CardId);
            _effects.RequireImplemented(card.CardId);
        }
        var rng = new SeededRandom(setup.Seed);
        var pile = setup.Cards.ToList();
        rng.Shuffle(pile);
        return new(
            Player: setup.Player, Life: 1000, Attack: _cards.Version == "1.1" ? 100 : 60, Defense: _cards.Version == "1.1" ? 40 : 20, Shield: 0, Energy: 0,
            DeckElementCount: setup.Cards.Select(card => _cards.Get(card.CardId).Element).Distinct(StringComparer.Ordinal).Count(),
            PrimaryElement: ResolvePrimaryElement(setup.Cards), ElementForgeActive: false, ElementForgeBonusLayers: 0,
            ElementForgePotentialLayers: ResolveForgePotentialLayers(setup.Cards),
            NextFire: _cards.Version == "1.1" ? 50 : 100, AttackIntervalModifier: 0, PermanentIntervalMultiplierPercent: 100, TemporaryIntervalMultiplierPercent: 100,
            NextIncomingDamageMultiplierPercent: 100, NextIncomingDamageFlat: 0,
            HealingReductionPercent: 0, HealingReductionUntilActionValue: 0,
            BattleIncomingDamageMultiplierPercent: 100, BattleIncomingDamageUntilActionValue: 0,
            TemporaryShield: 0, Tides: 0m, TideActive: false, NextTideDamageMultiplierPercent: 100, TideRefundPercent: 0, BloodTideActive: false, NextWaterShieldHealingMultiplierPercent: 100, ActualHealingThisBattle: 0m, CardsPlayedThisWindow: 0, GuardianBarrierActive: false, WarGodEmblemActive: false, RewindSnapshot: null, NextPoisonOnHitLayers: 0, NextPoisonOnHitCharges: 0, ExtraPoisonTickCharges: 0, PlagueLifeDamageActive: false, PoisonExplosionActive: false, PlagueActive: false, PlagueAttackReduction: 0, PlagueDefenseReduction: 0,
            NextDrawBonus: 0, NextEnergyBonus: 0, NextGapAdjustment: 0,
            WindLayers: 0, WaterLayers: 0, EarthLayers: 0, EarthBarrierActive: false, ShieldBreakReturnPercent: 0, ShieldBreakReturnFlat: 0, ShieldBreakDefenseMarkerActive: false, ShieldBreakDrawMarkerActive: false, ShieldBrokenThisBattle: false, FireLayers: 0, Embers: 0, EmberDamageActive: false, EmberCoreActive: false, AshRebirthUsed: false, AshCycleActive: false, ShuffleCount: 0, TemperBonusUses: 0, PoisonLayers: 0,
            PoisonEnchantmentLayers: 0, NextPoisonDecayActionValue: 0,
            PoisonDecayIntervalPercent: 0, PoisonDecayProtectionCharges: 0, PoisonDecayKeepLast: false,
            PoisonSpecialized: setup.Cards.Any(card => _cards.Get(card.CardId).Kind == CardKind.Specialization && _cards.Get(card.CardId).Element == "poison"),
            FireSpecialized: setup.Cards.Any(card => _cards.Get(card.CardId).Kind == CardKind.Specialization && _cards.Get(card.CardId).Element == "fire"),
            WaterSpecialized: setup.Cards.Any(card => _cards.Get(card.CardId).Kind == CardKind.Specialization && _cards.Get(card.CardId).Element == "water"),
            EarthSpecialized: setup.Cards.Any(card => _cards.Get(card.CardId).Kind == CardKind.Specialization && _cards.Get(card.CardId).Element == "earth"),
            WindSpecialized: setup.Cards.Any(card => _cards.Get(card.CardId).Kind == CardKind.Specialization && _cards.Get(card.CardId).Element == "wind"),
            BattleAttackReduction: 0, BattleDefenseReduction: 0, NegativeSuppressedUntilActionValue: 0,
            TemporaryAttackReduction: 0, TemporaryDefenseReduction: 0, TemporaryPoisonLayers: 0,
            FirstPlayed: Array.Empty<CardInstanceId>(), DrawPile: pile.AsReadOnly(),
            DiscardPile: Array.Empty<CardInstance>(), CurrentPool: Array.Empty<CardInstance>(),
            ExhaustedCards: Array.Empty<CardInstance>(), PendingSubmissiles: 0,
            PendingWindSubmissiles: 0, NextWindSubmissileFlat: 0, NextWindSubmissileAttackPercent: 0,
            WindTraceActive: false, WindTraceLayers: 0, WindTraceBonusLayers: 0, WindGaleActive: false, WindMainShotCount: 0, WindTraceExplosionMultiplierPercent: 0,
            WindArrowActive: false, NextShieldDamageMultiplierPercent: 0, WindChaseActive: false, LastMainMissileActionValue: -1, LastMainMissileActualDamage: 0, MainDamageBonusUntilDrawPercent: 0,
            NextMissileBonusPercent: 0, NextMissileBonusFlat: 0, NextMissileHealingPercent: 0,
            NextShieldPenetrationPercent: 0, MainShieldPenetrationUntilDrawPercent: 0, MainDefensePenetrationPercent: 0, NextDefensePenetrationPercent: 0, NextMainTemporaryShieldPercent: 0, RandomState: rng.State);
    }

    private string ResolvePrimaryElement(IReadOnlyList<CardInstance> cards)
    {
        var specialization = cards.Select(card => _cards.Get(card.CardId))
            .FirstOrDefault(definition => definition.Kind == CardKind.Specialization);
        if (specialization is not null) return specialization.Element;
        return cards.Select(card => _cards.Get(card.CardId))
            .Where(definition => definition.Layers > 0)
            .GroupBy(definition => definition.Element, StringComparer.Ordinal)
            .OrderByDescending(group => group.Sum(definition => definition.Layers))
            .ThenBy(group => group.Key, StringComparer.Ordinal)
            .Select(group => group.Key)
            .FirstOrDefault() ?? "generic";
    }

    private int ResolveForgePotentialLayers(IReadOnlyList<CardInstance> cards)
    {
        var primary = ResolvePrimaryElement(cards);
        return Math.Min(6, cards.Select(card => _cards.Get(card.CardId))
            .Where(definition => definition.Layers > 0 && definition.Element != primary)
            .Sum(definition => definition.Layers));
    }

    public IReadOnlyList<CardInstance> GetSearchCandidates(CombatState state, PlayerId player)
    {
        var self = GetPlayer(state, player);
        var candidates = self.DrawPile.Where(c => _cards.Get(c.CardId).Layers > 0).ToList();
        var rng = SeededRandom.FromState(self.RandomState);
        rng.Shuffle(candidates);
        return candidates.Take(3).ToArray();
    }

    public SearchSelectionSession? GetSearchSession(CombatState state, PlayerId player, CardInstanceId sourceCard)
    {
        var self = GetPlayer(state, player);
        var card = self.CurrentPool.FirstOrDefault(item => item.InstanceId == sourceCard);
        if (card is null || !CombatCardExecution.IsSearch(card.CardId)) return null;
        var candidates = SearchChoices(self, card.CardId);
        var maximum = card.CardId switch { "大检索" => 2, "命运检索" => 3, "禁咒目录" or "壁垒之心" => 2, _ => 1 };
        return new SearchSelectionSession(player, sourceCard, card.CardId, candidates, maximum, maximum > 1);
    }

    public CombatResolution Submit(CombatState state, CombatCommand command)
    {
        CombatResolution Reject(string code) => new(false, state, Array.Empty<CombatEvent>(), new(code, code));
        if (state.Phase == CombatPhase.Finished) return Reject("BattleAlreadyFinished");
        if (command.Battle != state.Battle) return Reject("WrongBattle");
        if (command.Player != state.A.Player && command.Player != state.B.Player) return Reject("UnknownPlayer");
        if (command.ExpectedRevision != state.Revision) return Reject("StaleCombatRevision");
        if (state.EndedWindows.Contains(command.Player)) return Reject("WindowAlreadyEnded");
        if (state.PendingActions.Any(p => p.Player == command.Player)) return Reject("ActionAlreadySubmitted");
        var self = GetPlayer(state, command.Player);
        if (command.Action.Kind == CombatActionKind.PlayCard)
        {
            var card = self.CurrentPool.FirstOrDefault(c => c.InstanceId == command.Action.Card);
            if (card is null) return Reject("CardNotInCurrentPool");
            if (_cards.Get(card.CardId).Cost > self.Energy) return Reject("InsufficientEnergy");
            if (card.CardId == "检索附魔")
            {
                var choices = GetSearchCandidates(state, command.Player);
                if (choices.Count > 0 && !choices.Any(c => c.InstanceId == command.Action.SearchTarget))
                    return Reject("InvalidSearchTarget");
                if (choices.Count == 0 && command.Action.SearchTarget is not null) return Reject("InvalidSearchTarget");
            }
            else if (card.CardId is "翻找" or "火种翻找" or "火种库" or "禁咒目录" or "壁垒之心" or "水之低语" or "小检索" or "大检索" or "命运检索" or "寻毒" or "寻风" or "寻岩" or "寻物")
            {
                if (command.Action.SearchTarget is not null && command.Action.SearchTargets is not null)
                    return Reject("AmbiguousSearchSelection");
                var choices = SearchChoices(self, card.CardId);
                if (command.Action.SearchTarget is { } target && !choices.Any(item => item.InstanceId == target))
                    return Reject("InvalidSearchTarget");
                if (command.Action.SearchTargets is { } targets)
                {
                    var max = card.CardId switch { "大检索" => 2, "命运检索" => 3, "禁咒目录" or "壁垒之心" => 2, _ => 0 };
                    if (max == 0 || targets.Count > max || targets.Distinct().Count() != targets.Count ||
                        targets.Any(targetId => !choices.Any(item => item.InstanceId == targetId)))
                        return Reject("InvalidSearchTargets");
                }
            }
            else if (command.Action.SearchTarget is not null || command.Action.SearchTargets is { Count: > 0 })
                return Reject("UnexpectedSearchTarget");
        }
        else if (command.Action.Kind != CombatActionKind.EndWindow || command.Action.Card is not null ||
                 command.Action.SearchTarget is not null || command.Action.SearchTargets is { Count: > 0 }) return Reject("InvalidCombatAction");

        var pending = state.PendingActions.Append(new PendingAction(command.Player, command.Action)).ToArray();
        var next = state with { PendingActions = pending };
        // Revision counts resolved steps. Both controllers submit against the same revision/snapshot.
        var required = 2 - state.EndedWindows.Count;
        if (pending.Length < required) return new(true, next, Array.Empty<CombatEvent>(), null);
        var events = new List<CombatEvent>();
        next = next with { Revision = state.Revision + 1 };
        // Paired submissions are simultaneous: establish rewind before resolving
        // any opposing lethal card, independent of submission/AI scheduling order.
        foreach (var action in pending.OrderByDescending(p => p.Action.Kind == CombatActionKind.PlayCard &&
                     GetPlayer(next, p.Player).CurrentPool.Any(c => c.InstanceId == p.Action.Card && c.CardId == "时光倒流")))
        {
            if (action.Action.Kind == CombatActionKind.EndWindow)
                next = next with { EndedWindows = next.EndedWindows.Append(action.Player).ToArray() };
            else
            {
                var updated = Play(GetPlayer(next, action.Player), action.Action, next, events);
                next = SetPlayer(next, updated.Source);
                next = SetPlayer(next, updated.Target);
            }
        }
        next = next with { PendingActions = Array.Empty<PendingAction>() };
        next = CheckDeath(ResolveAutomaticShieldBursts(next, events), events);
        if (next.Phase == CombatPhase.Finished) return new(true, next, events.AsReadOnly(), null);
        if (next.EndedWindows.Count == 2)
            next = CloseWindow(next, events);
        return new(true, next, events.AsReadOnly(), null);
    }

    private sealed record PlayResult(CombatantState Source, CombatantState Target);

    private PlayResult Play(CombatantState self, CombatAction action, CombatState state, List<CombatEvent> events)
    {
        var card = self.CurrentPool.Single(c => c.InstanceId == action.Card);
        var definition = _cards.Get(card.CardId);
        var attackBefore = self.Attack;
        self = self with
        {
            Attack = self.Attack + definition.Attack,
            Defense = self.Defense + definition.Defense,
            Energy = self.Energy - definition.Cost,
            CardsPlayedThisWindow = self.CardsPlayedThisWindow + 1,
            CurrentPool = self.CurrentPool.Where(c => c.InstanceId != card.InstanceId).ToArray(),
            DiscardPile = definition.Ability ? self.DiscardPile : self.DiscardPile.Append(card).ToArray(),
            ExhaustedCards = definition.Ability ? self.ExhaustedCards.Append(card).ToArray() : self.ExhaustedCards
        };
        if (definition.Layers > 0 && !self.FirstPlayed.Contains(card.InstanceId))
        {
            self = self with
            {
                FirstPlayed = self.FirstPlayed.Append(card.InstanceId).ToArray(),
                EarthLayers = self.EarthLayers + (definition.Element == "earth" ? definition.Layers : 0),
                WaterLayers = self.WaterLayers + (definition.Element == "water" ? definition.Layers : 0),
                WindLayers = self.WindLayers + (definition.Element == "wind" ? definition.Layers : 0)
                ,FireLayers = self.FireLayers + (definition.Element == "fire" ? definition.Layers : 0)
                ,PoisonEnchantmentLayers = self.PoisonEnchantmentLayers + (definition.Element == "poison" ? definition.Layers : 0)
            };
        }
        var targetState = state.A.Player == self.Player ? state.B : state.A;
        if (CombatCardExecution.HasPipeline(card.CardId))
        {
            var mutation = _pipeline.Resolve(new EffectContext(
                state.Battle, state.ActionValue, self.Player, targetState.Player, card,
                CombatResourceState.From(self), CombatResourceState.From(targetState)), EffectTiming.OnPlay).Single();
            self = ApplyResources(self, mutation.SourceResources);
            targetState = ApplyResources(targetState, mutation.TargetResources);
            events.AddRange(mutation.Events.Select(effectEvent => effectEvent with { Revision = state.Revision }));
        }
        if (card.CardId == "魔力契约") self = self with { ManaContractActive = true };
        if (CombatCardExecution.Deck.Contains(card.CardId)) switch (card.CardId)
        {
            case "重洗":
                self = ApplyShuffleTransaction(self, events, state);
                break;
            case "灰烬重生":
                self = ApplyShuffleTransaction(self, events, state);
                if (self.EmberDamageActive)
                    self = self with { Embers = Math.Min(5, self.Embers + 1) };
                break;
            case "回火":
                self = ApplyShuffleTransaction(self, events, state);
                if (self.FireSpecialized && self.ShuffleCount >= 3 && self.TemperBonusUses < 2)
                    self = self with { Embers = self.Embers + 1, TemperBonusUses = self.TemperBonusUses + 1 };
                break;
            case "余烬引擎":
                self = ApplyShuffleTransaction(self, events, state) with { NextDrawBonus = self.NextDrawBonus + 2, Energy = self.Energy + 2 };
                break;
            case "循环":
                self = ApplyShuffleTransaction(self, events, state);
                break;
            case "检索附魔":
            {
                var rng = SeededRandom.FromState(self.RandomState);
                var choices = self.DrawPile.Where(c => _cards.Get(c.CardId).Layers > 0).ToList();
                rng.Shuffle(choices);
                if (action.SearchTarget is { } target)
                {
                    var selected = self.DrawPile.Single(c => c.InstanceId == target);
                    self = self with { DrawPile = new[] { selected }.Concat(self.DrawPile.Where(c => c.InstanceId != target)).ToArray() };
                }
                self = self with { RandomState = rng.State };
                break;
            }
            case "翻找":
            {
                var viewed = self.DrawPile.Take(3).ToArray();
                var selected = viewed.FirstOrDefault(c => c.InstanceId == action.SearchTarget);
                if (selected is not null)
                    self = self with { DrawPile = new[] { selected }.Concat(self.DrawPile.Skip(viewed.Length))
                        .Concat(viewed.Where(c => c.InstanceId != selected.InstanceId)).ToArray() };
                break;
            }
            case "火种翻找":
                self = PlaceSearchTargetOnTop(self, SearchChoices(self, card.CardId), action.SearchTarget);
                self = AdvanceSearchRandom(self, card.CardId);
                break;
            case "火种库":
                self = PlaceSearchTargetOnTop(self, SearchChoices(self, card.CardId), action.SearchTarget);
                self = AdvanceSearchRandom(self, card.CardId);
                break;
            case "水之低语":
                self = PlaceSearchTargetOnTop(self, SearchChoices(self, card.CardId), action.SearchTarget);
                self = AdvanceSearchRandom(self, card.CardId);
                break;
            case "小检索":
                self = PlaceSearchTargetOnTop(self, SearchChoices(self, card.CardId), action.SearchTarget);
                self = AdvanceSearchRandom(self, card.CardId);
                break;
            case "大检索":
            case "命运检索":
                self = PlaceSearchTargetsOnTop(self, SearchChoices(self, card.CardId), action.SearchTargets);
                self = AdvanceSearchRandom(self, card.CardId);
                break;
            case "壁垒之心":
                self = PlaceSearchTargetsOnTop(self, SearchChoices(self, card.CardId), action.SearchTargets);
                self = AdvanceSearchRandom(self, card.CardId);
                break;
            case "禁咒目录":
                self = PlaceSearchTargetsOnTop(self, SearchChoices(self, card.CardId), action.SearchTargets);
                self = AdvanceSearchRandom(self, card.CardId);
                self = self with { NextEnergyBonus = self.NextEnergyBonus + 1 };
                break;
            case "寻毒":
            case "寻风":
            case "寻岩":
            case "寻物":
                self = PlaceSearchTargetOnTop(self, SearchChoices(self, card.CardId), action.SearchTarget);
                self = AdvanceSearchRandom(self, card.CardId);
                break;
        }
        if (_cards.Version == "1.1") self = ApplyAshStartupLink(self, card.CardId);
        events.Add(new(state.Revision, state.ActionValue, "CardPlayed", self.Player, card.CardId));
        return new PlayResult(self, targetState);
    }

    private static CombatantState ApplyAshStartupLink(CombatantState self, string played)
    {
        if (played is not ("灰烬循环" or "炽焰王冠")) return self;
        var owned = self.DrawPile.Concat(self.CurrentPool).Concat(self.DiscardPile).Concat(self.ExhaustedCards);
        if (!owned.Any(c => c.CardId == "灰烬循环")) return self;
        var target = played == "灰烬循环" ? "炽焰王冠" : "灰烬循环";
        if (!self.DrawnThisWindow.Contains(target) && !self.CurrentPool.Any(c => c.CardId == target)
            && !self.ExhaustedCards.Any(c => c.CardId == target))
        {
            var found = self.DrawPile.FirstOrDefault(c => c.CardId == target);
            if (found is not null)
                self = self with {DrawPile = new[]{found}.Concat(self.DrawPile.Where(c => c.InstanceId != found.InstanceId)).ToArray()};
        }
        return self;
    }

    private static CombatantState ApplyResources(CombatantState state, CombatResourceState resources) => state with
    {
        Life = resources.Life, Shield = resources.Shield, Attack = resources.Attack,
        Defense = resources.Defense, Energy = resources.Energy, DeckElementCount = resources.DeckElementCount, PrimaryElement = resources.PrimaryElement,
        ElementForgeActive = resources.ElementForgeActive, ElementForgeBonusLayers = resources.ElementForgeBonusLayers,
        ElementForgePotentialLayers = resources.ElementForgePotentialLayers, AttackIntervalModifier = resources.AttackIntervalModifier,
        PermanentIntervalMultiplierPercent = resources.PermanentIntervalMultiplierPercent,
        TemporaryIntervalMultiplierPercent = resources.TemporaryIntervalMultiplierPercent,
        NextIncomingDamageMultiplierPercent = resources.NextIncomingDamageMultiplierPercent,
        NextIncomingDamageFlat = resources.NextIncomingDamageFlat,
        HealingReductionPercent = resources.HealingReductionPercent,
        HealingReductionUntilActionValue = resources.HealingReductionUntilActionValue,
        BattleIncomingDamageMultiplierPercent = resources.BattleIncomingDamageMultiplierPercent,
        BattleIncomingDamageUntilActionValue = resources.BattleIncomingDamageUntilActionValue,
        TemporaryShield = resources.TemporaryShield,
        Tides = resources.Tides,
        TideActive = resources.TideActive,
        NextTideDamageMultiplierPercent = resources.NextTideDamageMultiplierPercent,
        TideRefundPercent = resources.TideRefundPercent,
        BloodTideActive = resources.BloodTideActive,
        NextWaterShieldHealingMultiplierPercent = resources.NextWaterShieldHealingMultiplierPercent,
        ActualHealingThisBattle = resources.ActualHealingThisBattle,
        CardsPlayedThisWindow = resources.CardsPlayedThisWindow,
        GuardianBarrierActive = resources.GuardianBarrierActive,
        WarGodEmblemActive = resources.WarGodEmblemActive,
        RewindSnapshot = resources.RewindSnapshot,
        NextPoisonOnHitLayers = resources.NextPoisonOnHitLayers,
        NextPoisonOnHitCharges = resources.NextPoisonOnHitCharges,
        ExtraPoisonTickCharges = resources.ExtraPoisonTickCharges,
        PlagueLifeDamageActive = resources.PlagueLifeDamageActive,
        PoisonExplosionActive = resources.PoisonExplosionActive,
        PlagueActive = resources.PlagueActive,
        PlagueAttackReduction = resources.PlagueAttackReduction,
        PlagueDefenseReduction = resources.PlagueDefenseReduction,
        WindLayers = resources.WindLayers, WaterLayers = resources.WaterLayers,
            EarthLayers = resources.EarthLayers, EarthBarrierActive = resources.EarthBarrierActive, ShieldBreakReturnPercent = resources.ShieldBreakReturnPercent, ShieldBreakReturnFlat = resources.ShieldBreakReturnFlat, ShieldBreakDefenseMarkerActive = resources.ShieldBreakDefenseMarkerActive, ShieldBreakDrawMarkerActive = resources.ShieldBreakDrawMarkerActive, ShieldBrokenThisBattle = resources.ShieldBrokenThisBattle, FireLayers = resources.FireLayers, Embers = resources.Embers, EmberDamageActive = resources.EmberDamageActive, EmberCoreActive = resources.EmberCoreActive, AshRebirthUsed = resources.AshRebirthUsed, AshCycleActive = resources.AshCycleActive, ShuffleCount = resources.ShuffleCount, TemperBonusUses = resources.TemperBonusUses,
        PoisonLayers = resources.PoisonLayers
        ,NextDrawBonus = resources.NextDrawBonus
        ,NextEnergyBonus = resources.NextEnergyBonus
        ,NextGapAdjustment = resources.NextGapAdjustment
        ,PendingSubmissiles = resources.PendingSubmissiles
        ,PendingWindSubmissiles = resources.PendingWindSubmissiles
        ,NextWindSubmissileFlat = resources.NextWindSubmissileFlat
        ,NextWindSubmissileAttackPercent = resources.NextWindSubmissileAttackPercent
        ,WindTraceActive = resources.WindTraceActive
        ,WindTraceLayers = resources.WindTraceLayers
        ,WindTraceBonusLayers = resources.WindTraceBonusLayers
        ,WindGaleActive = resources.WindGaleActive
        ,WindMainShotCount = resources.WindMainShotCount
        ,WindTraceExplosionMultiplierPercent = resources.WindTraceExplosionMultiplierPercent
        ,WindArrowActive = resources.WindArrowActive
        ,NextShieldDamageMultiplierPercent = resources.NextShieldDamageMultiplierPercent
        ,WindChaseActive = resources.WindChaseActive
        ,LastMainMissileActionValue = resources.LastMainMissileActionValue
        ,LastMainMissileActualDamage = resources.LastMainMissileActualDamage
        ,MainDamageBonusUntilDrawPercent = resources.MainDamageBonusUntilDrawPercent
        ,NextMissileBonusPercent = resources.NextMissileBonusPercent
        ,NextMissileBonusFlat = resources.NextMissileBonusFlat
        ,NextMissileHealingPercent = resources.NextMissileHealingPercent
        ,NextShieldPenetrationPercent = resources.NextShieldPenetrationPercent
        ,MainShieldPenetrationUntilDrawPercent = resources.MainShieldPenetrationUntilDrawPercent
        ,MainDefensePenetrationPercent = resources.MainDefensePenetrationPercent
        ,NextDefensePenetrationPercent = resources.NextDefensePenetrationPercent
        ,NextMainTemporaryShieldPercent = resources.NextMainTemporaryShieldPercent
        ,UnredeemedEmbersSpent = resources.UnredeemedEmbersSpent
        ,AshCyclePendingCredit = resources.AshCyclePendingCredit
        ,ShieldDecay = resources.ShieldDecay
        ,BastionHeartActive = resources.BastionHeartActive
        ,BurningBloodlineActive = resources.BurningBloodlineActive, LifeSpringActive = resources.LifeSpringActive, NextTideHealingRecordBonusPercent = resources.NextTideHealingRecordBonusPercent

        ,BattleAttackReduction = resources.BattleAttackReduction
        ,BattleDefenseReduction = resources.BattleDefenseReduction
        ,NegativeSuppressedUntilActionValue = resources.NegativeSuppressedUntilActionValue
        ,TemporaryAttackReduction = resources.TemporaryAttackReduction
        ,TemporaryDefenseReduction = resources.TemporaryDefenseReduction
        ,TemporaryPoisonLayers = resources.TemporaryPoisonLayers
        ,PoisonEnchantmentLayers = resources.PoisonEnchantmentLayers
        ,NextPoisonDecayActionValue = resources.NextPoisonDecayActionValue
        ,PoisonDecayIntervalPercent = resources.PoisonDecayIntervalPercent
        ,PoisonDecayProtectionCharges = resources.PoisonDecayProtectionCharges
        ,PoisonDecayKeepLast = resources.PoisonDecayKeepLast
        ,PoisonSpecialized = resources.PoisonSpecialized
        ,FireSpecialized = resources.FireSpecialized
        ,WaterSpecialized = resources.WaterSpecialized
        ,EarthSpecialized = resources.EarthSpecialized
        ,WindSpecialized = resources.WindSpecialized
    };

    private static CombatantState ApplyShuffleTransaction(CombatantState self, List<CombatEvent> events, CombatState state)
    {
        var before = self.RandomState;
        var rng = SeededRandom.FromState(before);
        var inputDraw = self.DrawPile.ToArray();
        var inputDiscard = self.DiscardPile.ToArray();
        var pile = inputDraw.Concat(inputDiscard).ToList();
        rng.Shuffle(pile);
        var transaction = new DeckRandomTransaction(before, rng.State, inputDraw, inputDiscard, pile.ToArray(), Array.Empty<CardInstance>());
        events.Add(new(state.Revision, state.ActionValue, "DeckShuffled", self.Player, Amount: transaction.OutputDrawPile.Count));
        var next = self with
        {
            DrawPile = transaction.OutputDrawPile,
            DiscardPile = transaction.OutputDiscardPile,
            RandomState = transaction.RandomAfter,
            ShuffleCount = self.ShuffleCount + 1
        };
        if (next.AshCycleActive && next.EmberDamageActive)
            next = next with { Embers = Math.Min(5, next.Embers + 2) };
        return next;
    }

    private IReadOnlyList<CardInstance> SearchChoices(CombatantState self, string cardId)
    {
        if (cardId == "翻找") return self.DrawPile.Take(3).ToArray();
        var candidates = self.DrawPile.ToList();
        if (cardId == "检索附魔") candidates = candidates.Where(card => _cards.Get(card.CardId).Layers > 0).ToList();
        if (cardId is "火种翻找" or "火种库") candidates = candidates.Where(card => _cards.Get(card.CardId).Element == "fire").ToList();
        if (cardId == "禁咒目录") candidates = candidates.Where(card => _cards.Get(card.CardId).Rarity >= CardRarity.Epic).ToList();
        if (cardId == "水之低语") candidates = candidates.Where(card => _cards.Get(card.CardId).Element == "water").ToList();
        if (cardId == "寻毒") candidates = candidates.Where(card => _cards.Get(card.CardId).Element == "poison").ToList();
        if (cardId == "寻风") candidates = candidates.Where(card => _cards.Get(card.CardId).Element == "wind").ToList();
        if (cardId is "寻岩" or "壁垒之心") candidates = candidates.Where(card => _cards.Get(card.CardId).Text.Contains("护盾", StringComparison.Ordinal)).ToList();
        if (cardId == "寻物") candidates = candidates.Where(card => _cards.Get(card.CardId).Rarity == CardRarity.Common).ToList();
        var count = cardId switch { "翻找" => 3, "火种翻找" or "水之低语" or "寻毒" or "寻风" or "寻岩" => 2, "火种库" => 4, "禁咒目录" or "壁垒之心" => 5, "大检索" => 5, "命运检索" => 7, _ => 3 };
        var rng = SeededRandom.FromState(self.RandomState);
        rng.Shuffle(candidates);
        return candidates.Take(count).ToArray();
    }

    private static CombatantState PlaceSearchTargetOnTop(
        CombatantState self,
        IReadOnlyList<CardInstance> candidates,
        CardInstanceId? target)
    {
        if (target is null || candidates.Count == 0) return self;
        var selected = candidates.FirstOrDefault(card => card.InstanceId == target);
        if (selected is null) return self;
        return self with
        {
            DrawPile = new[] { selected }.Concat(self.DrawPile.Where(card => card.InstanceId != selected.InstanceId)).ToArray()
        };
    }

    private CombatantState AdvanceSearchRandom(CombatantState self, string cardId)
    {
        var candidates = self.DrawPile.ToList();
        if (cardId is "火种翻找" or "火种库") candidates = candidates.Where(card => _cards.Get(card.CardId).Element == "fire").ToList();
        if (cardId == "禁咒目录") candidates = candidates.Where(card => _cards.Get(card.CardId).Rarity >= CardRarity.Epic).ToList();
        if (cardId == "水之低语") candidates = candidates.Where(card => _cards.Get(card.CardId).Element == "water").ToList();
        if (cardId == "寻毒") candidates = candidates.Where(card => _cards.Get(card.CardId).Element == "poison").ToList();
        if (cardId == "寻风") candidates = candidates.Where(card => _cards.Get(card.CardId).Element == "wind").ToList();
        if (cardId is "寻岩" or "壁垒之心") candidates = candidates.Where(card => _cards.Get(card.CardId).Text.Contains("护盾", StringComparison.Ordinal)).ToList();
        if (cardId == "寻物") candidates = candidates.Where(card => _cards.Get(card.CardId).Rarity == CardRarity.Common).ToList();
        var rng = SeededRandom.FromState(self.RandomState);
        rng.Shuffle(candidates);
        return self with { RandomState = rng.State };
    }

    private static CombatantState PlaceSearchTargetsOnTop(
        CombatantState self,
        IReadOnlyList<CardInstance> candidates,
        IReadOnlyList<CardInstanceId>? targets)
    {
        if (targets is null || targets.Count == 0) return self;
        var selected = targets
            .Select(target => candidates.FirstOrDefault(card => card.InstanceId == target))
            .Where(card => card is not null)
            .Cast<CardInstance>()
            .ToArray();
        if (selected.Length == 0) return self;
        return self with
        {
            DrawPile = selected.Concat(self.DrawPile.Where(card => selected.All(item => item.InstanceId != card.InstanceId))).ToArray()
        };
    }

    private static CombatantState Draw(CombatantState self)
    {
        if (self.TemporaryShield > 0)
            self = self with { Shield = Math.Max(0, self.Shield - self.TemporaryShield), TemporaryShield = 0 };
        var ashCredit = self.AshCycleActive ? Math.Min(3, self.AshCyclePendingCredit) : 0;
        var drawState = self with { AshCyclePendingCredit = 0 };
        var pile = self.DrawPile.ToList();
        var discard = self.DiscardPile.ToList();
        var pool = new List<CardInstance>();
        var rng = SeededRandom.FromState(self.RandomState);
        for (var i = 0; i < 5 + self.NextDrawBonus + ashCredit - (self.ManaContractActive ? 1 : 0); i++)
        {
            if (pile.Count == 0)
            {
                pile.AddRange(discard); discard.Clear(); rng.Shuffle(pile);
            }
            if (pile.Count == 0) break;
            pool.Add(pile[0]); pile.RemoveAt(0);
        }
        drawState = CombatTriggerRegistry.Consume(drawState, TemporaryTrigger.NextDraw);
        drawState = drawState with { MainDamageBonusUntilDrawPercent = 0, MainShieldPenetrationUntilDrawPercent = 0 };
        return drawState with { DrawPile = pile.AsReadOnly(), DiscardPile = discard.AsReadOnly(),
            CurrentPool = pool.AsReadOnly(), DrawnThisWindow = pool.Select(c=>c.CardId).ToArray(), Energy = 3 + self.NextEnergyBonus + ashCredit + (self.ManaContractActive ? 1 : 0),
            RandomState = rng.State };
    }

    private static CombatantState ExpireTemporaryNegativeStatuses(CombatantState self, int actionValue)
    {
        if (self.NegativeSuppressedUntilActionValue != 0 && actionValue >= self.NegativeSuppressedUntilActionValue)
            self = self with { NegativeSuppressedUntilActionValue = 0 };
        return self with
        {
            TemporaryAttackReduction = 0,
            TemporaryDefenseReduction = 0,
            TemporaryPoisonLayers = 0
        };
    }

    private static CombatantState ResolveWindowEndStats(CombatantState self)
    {
        if (self.GuardianBarrierActive && self.CardsPlayedThisWindow <= 2)
            self = self with { Defense = self.Defense + (4 - self.CardsPlayedThisWindow) };
        if (self.WarGodEmblemActive && self.CardsPlayedThisWindow >= 3)
            self = self with { Attack = self.Attack + 2 + self.CardsPlayedThisWindow };
        return self with { CardsPlayedThisWindow = 0 };
    }

    private static int CalculatePoisonDecayTime(int actionValue, int layers, int intervalPercent) =>
        layers <= 0 ? 0 : actionValue + Math.Max(1, CombatMath.Floor(CombatMath.Floor(200m / layers) * (1 + intervalPercent / 100m)));

    private static CombatState ResolvePoisonTick(CombatState state, int actionValue, List<CombatEvent> events)
    {
        var first = ResolvePoisonForTarget(state.B, state.A, actionValue, state.Revision, events);
        var second = ResolvePoisonForTarget(state.A, state.B, actionValue, state.Revision, events);
        var nextA = first.Target with { ExtraPoisonTickCharges = second.Source.ExtraPoisonTickCharges };
        var nextB = second.Target with { ExtraPoisonTickCharges = first.Source.ExtraPoisonTickCharges };
        return state with { A = nextA, B = nextB };
    }

    private static (CombatantState Source, CombatantState Target) ResolvePoisonForTarget(CombatantState source, CombatantState target,
        int actionValue, long revision, List<CombatEvent> events)
    {
        if (target.PoisonLayers <= 0)
        {
            if (target.PlagueAttackReduction != 0 || target.PlagueDefenseReduction != 0)
                target = target with
                {
                    Attack = target.Attack + target.PlagueAttackReduction,
                    Defense = target.Defense + target.PlagueDefenseReduction,
                    BattleAttackReduction = Math.Max(0, target.BattleAttackReduction - target.PlagueAttackReduction),
                    BattleDefenseReduction = Math.Max(0, target.BattleDefenseReduction - target.PlagueDefenseReduction),
                    PlagueAttackReduction = 0, PlagueDefenseReduction = 0
                };
            return (source, target);
        }
        if (source.PlagueActive && source.PoisonEnchantmentLayers > 0)
        {
            var desiredAttack = CombatMath.Floor(2m + (source.PoisonDecayKeepLast ? 0.6m : 0.4m) * source.PoisonEnchantmentLayers * target.PoisonLayers);
            var desiredDefense = CombatMath.Floor(2m + (source.PoisonDecayKeepLast ? 0.4m : 0.2m) * source.PoisonEnchantmentLayers * target.PoisonLayers);
            var attackDelta = desiredAttack - target.PlagueAttackReduction;
            var defenseDelta = desiredDefense - target.PlagueDefenseReduction;
            target = target with
            {
                Attack = Math.Max(0, target.Attack - attackDelta),
                Defense = Math.Max(0, target.Defense - defenseDelta),
                BattleAttackReduction = target.BattleAttackReduction + attackDelta,
                BattleDefenseReduction = target.BattleDefenseReduction + defenseDelta,
                PlagueAttackReduction = desiredAttack,
                PlagueDefenseReduction = desiredDefense
            };
        }
        if (source.PoisonEnchantmentLayers > 0)
        {
            var ratio = source.PoisonSpecialized ? 0.02m : 0.01m;
            var raw = source.Attack * source.PoisonEnchantmentLayers * target.PoisonLayers * ratio;
            if (source.PlagueLifeDamageActive)
                raw += 1000m * 0.01m * target.PoisonLayers;
            var damage = CombatMath.PoisonDamage(raw, target.Defense);
            target = target with { Life = target.Life - damage };
            events.Add(new(revision, actionValue, "PoisonDamage", source.Player, Amount: damage, LifeDamage: damage));
            if (source.ExtraPoisonTickCharges > 0)
            {
                var extraDamage = CombatMath.PoisonDamage(raw, target.Defense);
                target = target with { Life = target.Life - extraDamage };
                source = source with { ExtraPoisonTickCharges = source.ExtraPoisonTickCharges - 1 };
                events.Add(new(revision, actionValue, "PoisonExtraDamage", source.Player, Amount: extraDamage, LifeDamage: extraDamage));
            }
        }
        if (target.NextPoisonDecayActionValue != 0 && actionValue >= target.NextPoisonDecayActionValue)
        {
                if (target.PoisonDecayKeepLast && target.PoisonLayers <= 1)
                {
                    target = target with { NextPoisonDecayActionValue = 0 };
                    events.Add(new(revision, actionValue, "PoisonDecayRetained", target.Player, Amount: target.PoisonLayers));
                    return (source, target);
                }
                if (target.PoisonDecayProtectionCharges > 0)
                {
                    var layers = target.PoisonLayers + 1;
                    target = target with { PoisonLayers = layers, PoisonDecayProtectionCharges = target.PoisonDecayProtectionCharges - 1,
                        NextPoisonDecayActionValue = CalculatePoisonDecayTime(actionValue, layers, target.PoisonDecayIntervalPercent) };
                    events.Add(new(revision, actionValue, "PoisonDecayPrevented", target.Player, Amount: 1));
                }
                else
                {
                    var layers = Math.Max(0, target.PoisonLayers - 1);
                    target = target with { PoisonLayers = layers,
                        NextPoisonDecayActionValue = CalculatePoisonDecayTime(actionValue, layers, target.PoisonDecayIntervalPercent) };
                    if (source.PoisonExplosionActive)
                        source = source with { Attack = source.Attack + 1 };
                    events.Add(new(revision, actionValue, "PoisonDecay", target.Player, Amount: 1));
                }
        }
        return (source, target);
    }

    private static CombatantState ReturnUnused(CombatantState self) => self with
    {
        DrawPile = self.DrawPile.Concat(self.CurrentPool).ToArray(), CurrentPool = Array.Empty<CardInstance>(), Energy = 0
    };

    private CombatState CloseWindow(CombatState state, List<CombatEvent> events)
    {
        state = state with { A = ReturnUnused(state.A), B = ReturnUnused(state.B) };
        // At a draw-window action value, poison resolves after all cards for that
        // window have been submitted, but before fatigue and synchronized fire.
        // Earth's current-window shield is prepared later by the fire policy.
        if (state.ActionValue > 0 && state.ActionValue % 100 == 0)
            state = ResolvePoisonTick(state, state.ActionValue, events);
        if (state.ActionValue >= 1500)
        {
            state = state with { A = Fatigue(state.A, state, events), B = Fatigue(state.B, state, events) };
        }
        // Fire due at this timestamp after draw/play/fatigue, then judge the complete group.
        state = Fire(state, events);
        state = CheckDeath(state, events);
        while (state.Phase != CombatPhase.Finished)
        {
            var nextDraw = (state.ActionValue / 100 + 1) * 100;
            var time = Math.Min(nextDraw, Math.Min(state.A.NextFire, state.B.NextFire));
            state = state with { ActionValue = time };
            if (time == nextDraw)
            {
                var a = ExpireTemporaryNegativeStatuses(state.A, time);
                var b = ExpireTemporaryNegativeStatuses(state.B, time);
                a = ResolveWindowEndStats(a);
                b = ResolveWindowEndStats(b);
                return state with { A = Draw(a), B = Draw(b), EndedWindows = Array.Empty<PlayerId>() };
            }
            state = CheckDeath(Fire(state, events), events);
        }
        return state;
    }

    private static CombatantState Fatigue(CombatantState self, CombatState state, List<CombatEvent> events)
    {
        var loss = CombatMath.FatigueLoss(self.Life, state.ActionValue);
        events.Add(new(state.Revision, state.ActionValue, "Fatigue", self.Player, Amount: loss));
        return self with { Life = self.Life - loss };
    }

    private CombatState Fire(CombatState state, List<CombatEvent> events)
    {
        var aDue = state.A.NextFire == state.ActionValue;
        var bDue = state.B.NextFire == state.ActionValue;
        var a = _resolutionPolicy.PrepareBeforeFire(state.A, aDue);
        var b = _resolutionPolicy.PrepareBeforeFire(state.B, bDue);
        var aAfter = a;
        var bAfter = b;
        if (aDue) (aAfter, bAfter) = Hit(a, bAfter, state, events);
        if (bDue)
        {
            var hit = Hit(b, aAfter, state, events);
            // Both outgoing packets were formed from the pre-damage snapshot.
            bAfter = hit.Source with
            {
                Life = bAfter.Life + (hit.Source.Life - b.Life),
                Shield = Math.Max(0, bAfter.Shield + hit.Source.Shield - b.Shield),
                TemporaryShield = Math.Max(0, bAfter.TemporaryShield + hit.Source.TemporaryShield - b.TemporaryShield),
                Attack = bAfter.Attack + hit.Source.Attack - b.Attack,
                Defense = bAfter.Defense + hit.Source.Defense - b.Defense,
                PoisonLayers = bAfter.PoisonLayers + hit.Source.PoisonLayers - b.PoisonLayers,
                NextPoisonDecayActionValue = bAfter.NextPoisonDecayActionValue,
                NextDrawBonus = bAfter.NextDrawBonus + hit.Source.NextDrawBonus - b.NextDrawBonus,
                AshCyclePendingCredit = Math.Min(3, bAfter.AshCyclePendingCredit + hit.Source.AshCyclePendingCredit - b.AshCyclePendingCredit),
                ShieldBrokenThisBattle = bAfter.ShieldBrokenThisBattle || hit.Source.ShieldBrokenThisBattle,
                ShieldBreakDefenseMarkerActive = bAfter.ShieldBreakDefenseMarkerActive,
                ShieldBreakDrawMarkerActive = bAfter.ShieldBreakDrawMarkerActive,
                NextIncomingDamageMultiplierPercent = bAfter.NextIncomingDamageMultiplierPercent,
                NextIncomingDamageFlat = bAfter.NextIncomingDamageFlat,
                BattleIncomingDamageMultiplierPercent = bAfter.BattleIncomingDamageMultiplierPercent,
                BattleIncomingDamageUntilActionValue = bAfter.BattleIncomingDamageUntilActionValue
            };
            aAfter = hit.Target;
        }
        if (aDue) aAfter = FinishFire(aAfter, state.ActionValue);
        if (bDue) bAfter = FinishFire(bAfter, state.ActionValue);
        return ResolveAutomaticShieldBursts(state with { A = aAfter, B = bAfter }, events);
    }

    private static CombatState ResolveAutomaticShieldBursts(CombatState state, List<CombatEvent> events)
    {
        var packets = new List<(PlayerId Source, int Damage, int Shield, int Life)>();
        foreach (var source in new[] { state.A, state.B })
        {
            var target = source.Player == state.A.Player ? state.B : state.A;
            if (!source.EarthBarrierActive || source.Shield <= 0 || source.Life <= 0 || target.Life <= 0) continue;
            var upgraded = source.EarthSpecialized && source.ShieldBreakReturnPercent > 0;
            var raw = Math.Max(0, source.Shield * source.EarthLayers * (upgraded ? 0.045m : 0.03m)
                - target.Defense * 0.50m);
            var damage = CombatMath.Ceiling(raw * (1 + source.FireLayers * (source.FireSpecialized ? 0.02m : 0.01m)));
            var split = CombatMath.SplitShieldBurst(damage, target.Shield, 0);
            if (split.Life >= target.Life) packets.Add((source.Player, damage, split.Shield, split.Life));
        }
        foreach (var packet in packets)
        {
            // The automatic shield burst consumes the barrier and shield only;
            // it must not overwrite the owner's live defense stat.
            var source = GetPlayer(state, packet.Source) with { Shield = 0, TemporaryShield = 0 };
            var targetId = packet.Source == state.A.Player ? state.B.Player : state.A.Player;
            var target = GetPlayer(state, targetId);
            target = target with { Shield = Math.Max(0, target.Shield - packet.Shield),
                TemporaryShield = Math.Max(0, target.TemporaryShield - packet.Shield), Life = target.Life - packet.Life };
            state = SetPlayer(SetPlayer(state, source), target);
            events.Add(new(state.Revision, state.ActionValue, "AutomaticShieldExecute", packet.Source,
                Amount: packet.Damage, ShieldDamage: packet.Shield, LifeDamage: packet.Life));
        }
        return state;
    }

    private static (CombatantState Source, CombatantState Target) Hit(CombatantState source,
        CombatantState target, CombatState state, List<CombatEvent> events)
    {
        var lifeDamage = 0;
        var shieldDamage = 0;
        var emberSpent = 0;
        var mainActualDamage = 0;
        var pendingEarthReflect = 0;
        for (var i = 0; i <= source.PendingSubmissiles; i++)
        {
            var raw = i == 0 ? source.Attack * (source.BurningBloodlineActive ? 1.8m : 1m) : 15 + source.Attack * 0.20m;
            if (i == 0) raw += source.ShieldDecay.MainDamage;
            raw = (raw * (1 + source.NextMissileBonusPercent / 100m)) + source.NextMissileBonusFlat;
            var defensePenetration = i == 0 ? source.NextDefensePenetrationPercent + source.MainDefensePenetrationPercent : 0;
            if (source.WindArrowActive)
                defensePenetration += CombatMath.Floor(source.WindLayers * (source.WindSpecialized ? 2m : 1m));
            var independentDefenseIgnore = source.WindArrowActive && source.WindGaleActive ? 15 : 0;
            var damage = CombatMath.MissileDamage(raw, target.Defense, defensePenetration, independentDefenseIgnore);
            if (i == 0 && source.WindChaseActive && source.LastMainMissileActionValue >= 0)
            {
                var elapsed = Math.Max(0, state.ActionValue - source.LastMainMissileActionValue);
                var factor = Math.Max(0m, 1m - elapsed / 50m);
                damage += CombatMath.Floor(source.LastMainMissileActualDamage * factor * 0.20m);
            }
            var tideSpent = 0;
            if (i == 0 && source.TideActive && source.Tides > 0)
            {
                tideSpent = CombatMath.Floor(source.Tides);
                damage = CombatMath.Floor(damage + tideSpent * (source.NextTideDamageMultiplierPercent / 100m));
                source = source with { Tides = source.TideRefundPercent > 0 ? CombatMath.Ceiling(tideSpent * source.TideRefundPercent / 100m) : 0m, NextTideDamageMultiplierPercent = 100 };
            }
            if (i == 0 && source.BloodTideActive)
            {
                var payment = Math.Max(1, CombatMath.Ceiling(source.Life * 0.04m));
                source = source with { Life = Math.Max(1, source.Life - payment) };
                damage += CombatMath.Ceiling(payment * 0.80m);
            }
            // Direct additions (tide, blood-tide payment and route/card flat
            // additions already included in raw) enter the ordinary missile
            // increase zone before it is consumed for shield/life splitting.
            if (i == 0 && source.MainDamageBonusUntilDrawPercent > 0)
                damage = Math.Max(1, CombatMath.Floor(damage * (1 + source.MainDamageBonusUntilDrawPercent / 100m)));
            if (target.BattleIncomingDamageUntilActionValue > state.ActionValue && target.BattleIncomingDamageMultiplierPercent != 100)
            {
                damage = Math.Max(1, CombatMath.Floor(damage * target.BattleIncomingDamageMultiplierPercent / 100m));
                target = target with { BattleIncomingDamageMultiplierPercent = 100, BattleIncomingDamageUntilActionValue = 0 };
            }
            var bastionReduction = target.BastionHeartActive && target.Shield > 0 ? 15 : 0;
            if (target.NextIncomingDamageMultiplierPercent != 100 || target.NextIncomingDamageFlat != 0 || bastionReduction > 0)
            {
                damage = Math.Max(1, CombatMath.Floor(damage * Math.Max(0, target.NextIncomingDamageMultiplierPercent - bastionReduction) / 100m) - target.NextIncomingDamageFlat);
                target = target with { NextIncomingDamageMultiplierPercent = 100, NextIncomingDamageFlat = 0 };
            }
            if (i == 0 && source.EmberDamageActive && source.Embers > 0)
            {
                emberSpent = source.Embers;
                damage = CombatMath.Floor(damage * (1 + source.FireLayers * (source.BurningBloodlineActive ? 0.03m : 0.025m) * emberSpent));
            }
            var shieldBefore = target.Shield;
            var shieldPenetration = i == 0 ? source.NextShieldPenetrationPercent + source.MainShieldPenetrationUntilDrawPercent : 0;
            // Wind Arrow uses only the base wind shield penetration.
            var split = CombatMath.SplitDamage(damage, target.Shield, source.WindLayers, source.WindSpecialized, shieldPenetration);
            var finalLife = CombatMath.Floor(split.Life * (1 + source.FireLayers * (source.FireSpecialized ? 0.02m : 0.01m)));
            finalLife = split.Life > 0 ? Math.Max(1, finalLife) : 0;
            var shieldBonusPercent = source.NextShieldDamageMultiplierPercent + (source.WindArrowActive ? 15 : 0);
            var actualShieldDamage = shieldBonusPercent > 0
                ? Math.Min(target.Shield, CombatMath.Ceiling(split.Shield * (1 + shieldBonusPercent / 100m)))
                : split.Shield;
            target = target with { Shield = target.Shield - actualShieldDamage, Life = target.Life - finalLife };
            target = ResolveShieldHitReactions(source, target, shieldBefore, actualShieldDamage, state, events, ref pendingEarthReflect);
            if (i == 0) { lifeDamage += finalLife; shieldDamage += actualShieldDamage; }
            if (i == 0) mainActualDamage = finalLife + actualShieldDamage;
            if (i == 0 && source.WindTraceActive)
            {
                var traceLayers = source.WindTraceLayers + 1 + source.WindTraceBonusLayers;
                source = source with { WindTraceLayers = traceLayers, WindTraceBonusLayers = 0 };
                if (traceLayers >= 3)
                {
                    var traceDamage = CombatMath.Floor(source.Attack * (0.08m * traceLayers + 0.02m * traceLayers * (traceLayers - 1) / 2m) * (1 + source.WindTraceExplosionMultiplierPercent / 100m));
                    target = target with { Life = target.Life - traceDamage };
                    events.Add(new(state.Revision, state.ActionValue, "WindTraceExplosion", source.Player, Amount: traceDamage, LifeDamage: traceDamage));
                    source = source with { WindTraceLayers = 0, WindTraceExplosionMultiplierPercent = 0 };
                }
            }
            events.Add(new(state.Revision, state.ActionValue, i == 0 ? "MainMissile" : "Submissile",
                source.Player, Amount: damage, ShieldDamage: actualShieldDamage, LifeDamage: finalLife));
            if (tideSpent > 0)
                events.Add(new(state.Revision, state.ActionValue, "TideSpent", source.Player, Amount: tideSpent));
        }
        if (source.WindGaleActive)
        {
            var shotCount = source.WindMainShotCount + 1;
            source = source with { WindMainShotCount = shotCount };
            if (shotCount % 3 == 0)
            {
                var trueDamage = CombatMath.Floor(source.Attack * 0.20m);
                target = target with { Life = target.Life - trueDamage };
                lifeDamage += trueDamage;
                events.Add(new(state.Revision, state.ActionValue, "WindGaleTrueShot", source.Player,
                    Amount: trueDamage, LifeDamage: trueDamage));
            }
        }
        if (source.WindChaseActive)
            source = source with { LastMainMissileActionValue = state.ActionValue, LastMainMissileActualDamage = mainActualDamage };
        if (source.NextMissileHealingPercent > 0)
        {
            var healing = mainActualDamage >= 80
                ? CombatMath.Ceiling((1000 - source.Life) * source.NextMissileHealingPercent / 100m)
                : 0;
            if (source.HealingReductionUntilActionValue > state.ActionValue)
                healing = CombatMath.Floor(healing * Math.Max(0, 100 - source.HealingReductionPercent) / 100m);
            var actualHealing = Math.Min(1000 - source.Life, Math.Max(0, healing));
            source = source with
            {
                Life = source.Life + actualHealing,
                ActualHealingThisBattle = source.ActualHealingThisBattle + actualHealing,
                NextMissileHealingPercent = 0
            };
            if (actualHealing > 0)
                events.Add(new(state.Revision, state.ActionValue, "ConditionalMissileHealing", source.Player, Amount: actualHealing, LifeDamage: 0));
        }
        if (emberSpent > 0)
        {
            source = EmberConsumption.Record(source, emberSpent);
            source = source with { Embers = 0 };
            if (source.EmberCoreActive)
            {
                // The route heals one layer at a time. Each layer reads the
                // remaining missing life after the previous layer resolves.
                for (var i = 0; i < emberSpent; i++)
                {
                    var heal = CombatMath.Ceiling((1000 - source.Life) * 0.10m);
                    source = source with { Life = Math.Min(1000, source.Life + heal) };
                }
            }
            events.Add(new(state.Revision, state.ActionValue, "EmberSpent", source.Player, Amount: emberSpent));
        }
        if (source.EmberCoreActive && source.FireSpecialized && mainActualDamage >= 160)
        {
            source = source with { Embers = source.Embers + 1 };
            events.Add(new(state.Revision, state.ActionValue, "EmberGenerated", source.Player, Amount: 1));
        }
        for (var i = 0; i < source.PendingWindSubmissiles; i++)
        {
            var raw = source.NextWindSubmissileFlat + source.Attack * (source.NextWindSubmissileAttackPercent / 100m);
            if (raw <= 0) raw = 18 + source.Attack * 0.20m;
            var defensePenetration = source.WindArrowActive ? CombatMath.Floor(source.WindLayers * (source.WindSpecialized ? 2m : 1m)) : 0;
            var independentDefenseIgnore = source.WindArrowActive && source.WindGaleActive ? 15 : 0;
            var damage = CombatMath.MissileDamage(raw, target.Defense, defensePenetration, independentDefenseIgnore);
            if (target.BastionHeartActive && target.Shield > 0)
                damage = Math.Max(1, CombatMath.Floor(damage * 0.85m));
            var shieldBefore = target.Shield;
            var split = CombatMath.SplitDamage(damage, target.Shield, source.WindLayers, source.WindSpecialized);
            var finalLife = CombatMath.Floor(split.Life * (1 + source.FireLayers * (source.FireSpecialized ? 0.02m : 0.01m)));
            finalLife = split.Life > 0 ? Math.Max(1, finalLife) : 0;
            var actualShieldDamage = Math.Min(target.Shield, CombatMath.Ceiling(split.Shield * (1 + (source.NextShieldDamageMultiplierPercent + (source.WindArrowActive ? 15 : 0)) / 100m)));
            target = target with { Shield = target.Shield - actualShieldDamage, Life = target.Life - finalLife };
            target = ResolveShieldHitReactions(source, target, shieldBefore, actualShieldDamage, state, events, ref pendingEarthReflect);
            if (source.WindTraceActive)
            {
                var traceLayers = source.WindTraceLayers + 1 + source.WindTraceBonusLayers;
                source = source with { WindTraceLayers = traceLayers, WindTraceBonusLayers = 0 };
                if (traceLayers >= 3)
                {
                    var traceRaw = Enumerable.Range(1, traceLayers)
                        .Sum(layer => source.Attack * (0.08m + (layer - 1) * 0.02m));
                    var traceDamage = CombatMath.Floor(traceRaw * (1 + source.WindTraceExplosionMultiplierPercent / 100m));
                    target = target with { Life = target.Life - traceDamage };
                    events.Add(new(state.Revision, state.ActionValue, "WindTraceExplosion", source.Player,
                        Amount: traceDamage, LifeDamage: traceDamage));
                    source = source with { WindTraceLayers = 0, WindTraceExplosionMultiplierPercent = 0 };
                }
            }
            events.Add(new(state.Revision, state.ActionValue, "WindSubmissile", source.Player,
                Amount: damage, ShieldDamage: actualShieldDamage, LifeDamage: finalLife));
        }
        if (pendingEarthReflect > 0)
        {
            var split = CombatMath.SplitShieldBurst(pendingEarthReflect, source.Shield,
                0);
            source = source with { Life = source.Life - split.Life, Shield = source.Shield - split.Shield,
                TemporaryShield = Math.Max(0, source.TemporaryShield - split.Shield) };
            events.Add(new(state.Revision, state.ActionValue, "EarthReflect", target.Player,
                Amount: pendingEarthReflect, ShieldDamage: split.Shield, LifeDamage: split.Life));
        }
        if (lifeDamage > 0 && source.PoisonEnchantmentLayers > 0)
        {
            var addedPoison = 1;
            if (source.NextPoisonOnHitCharges > 0)
            {
                addedPoison += source.NextPoisonOnHitLayers;
                source = source with { NextPoisonOnHitCharges = source.NextPoisonOnHitCharges - 1 };
            }
            var nextPoison = target.PoisonLayers + addedPoison;
            if (source.PoisonExplosionActive && addedPoison > 0)
                source = source with { Attack = source.Attack + addedPoison };
            target = target with
            {
                PoisonLayers = nextPoison,
                NextPoisonDecayActionValue = CalculatePoisonDecayTime(state.ActionValue, nextPoison, target.PoisonDecayIntervalPercent)
            };
            events.Add(new(state.Revision, state.ActionValue, "PoisonApplied", source.Player, Amount: addedPoison));
        }
        if (source.WaterLayers > 0)
        {
            var basis = lifeDamage + (shieldDamage * 3 * source.NextWaterShieldHealingMultiplierPercent / 100m);
            var healingRate = source.BloodTideActive && source.WaterSpecialized ? 0.06m : (source.WaterSpecialized ? 0.04m : 0.02m);
            var healing = CombatMath.Ceiling(basis * source.WaterLayers * healingRate);
            if (source.HealingReductionUntilActionValue > state.ActionValue)
                healing = CombatMath.Floor(healing * Math.Max(0, 100 - source.HealingReductionPercent) / 100m);
            var actualHealing = Math.Min(1000 - source.Life, healing);
            source = source with { Life = source.Life + actualHealing, ActualHealingThisBattle = source.ActualHealingThisBattle + actualHealing };
            source = source with { NextWaterShieldHealingMultiplierPercent = 100 };
            if (source.TideActive)
                source = source with { Tides = source.Tides + actualHealing * source.WaterLayers * (source.WaterSpecialized && source.TideRefundPercent > 0 ? 0.08m : 0.05m) * (1 + source.NextTideHealingRecordBonusPercent / 100m) };
        }
        source = source with { NextTideHealingRecordBonusPercent = 0 };
        return (source, target);
    }

    private static CombatantState ResolveShieldHitReactions(CombatantState source, CombatantState target,
        int shieldBefore, int actualShieldDamage, CombatState state, List<CombatEvent> events, ref int pendingEarthReflect)
    {
            if (shieldBefore > 0 && target.Shield == 0 && actualShieldDamage >= shieldBefore)
            {
                target = target with { ShieldBrokenThisBattle = true };
                if (target.ShieldBreakDefenseMarkerActive)
                    target = target with { Defense = target.Defense + 6, ShieldBreakDefenseMarkerActive = false };
                if (target.ShieldBreakDrawMarkerActive)
                    target = target with { NextDrawBonus = target.NextDrawBonus + 1, ShieldBreakDrawMarkerActive = false };
            }
            var absorptionReflect = target.EarthBarrierActive && target.EarthSpecialized && target.BastionHeartActive;
            if (absorptionReflect && actualShieldDamage > 0)
                pendingEarthReflect += CombatMath.Ceiling(Math.Max(0, actualShieldDamage * 0.025m * target.EarthLayers - source.Defense * 0.50m)
                    * (1 + target.FireLayers * (target.FireSpecialized ? 0.02m : 0.01m)));
            if (target.EarthBarrierActive && shieldBefore > 0 && target.Shield == 0 && actualShieldDamage >= shieldBefore)
            {
                var upgradedReflect = target.EarthSpecialized && target.ShieldBreakReturnPercent > 0;
                var reflectRate = upgradedReflect ? 0.045m : 0.03m;
                var defenseRate = 0.50m;
                var reflected = CombatMath.Ceiling(Math.Max(0, shieldBefore * reflectRate * target.EarthLayers - source.Defense * defenseRate)
                    * (1 + target.FireLayers * (target.FireSpecialized ? 0.02m : 0.01m)));
                if (reflected > 0 && !absorptionReflect)
                {
                    pendingEarthReflect += reflected;
                }
                var returnShield = Math.Max(target.ShieldBreakReturnFlat, CombatMath.Ceiling(shieldBefore * target.ShieldBreakReturnPercent / 100m));
                if (returnShield > 0)
                {
                    target = target with { ShieldDecay = target.ShieldDecay.OnOrdinaryGain(target.Shield), Shield = CombatMath.AddOrdinaryShield(target.Shield, returnShield) };
                    events.Add(new(state.Revision, state.ActionValue, "ShieldBreakReturn", target.Player, Amount: returnShield));
                }
            }

        return target;
    }

    private CombatantState FinishFire(CombatantState self, int time)
    {
        var additive = (_cards.Version == "1.1" ? 50m : 100m) + self.AttackIntervalModifier + self.NextGapAdjustment;
        if (self.BurningBloodlineActive) additive += 50;
        if (self.LifeSpringActive) additive -= 4 + 0.5m * self.WaterLayers;
        if (self.WindGaleActive) additive -= self.WindChaseActive ? 6 + 1.5m * self.WindLayers : 4 + self.WindLayers;
        var nextFire = checked(time + Math.Max(1,
            CombatMath.Floor(additive * self.PermanentIntervalMultiplierPercent * self.TemporaryIntervalMultiplierPercent / 10000m)));
        return CombatTriggerRegistry.Consume(self, TemporaryTrigger.NextFire) with
        { NextFire = nextFire, ShieldDecay = self.ShieldDecay.AfterFire() };
    }

    private static CombatState CheckDeath(CombatState state, List<CombatEvent> events)
    {
        if (state.ActionValue >= 0)
        {
            var a = TryRewind(state.A, state.ActionValue, events, state.Revision);
            var b = TryRewind(state.B, state.ActionValue, events, state.Revision);
            state = state with { A = a, B = b };
        }
        if (state.A.Life > 0 && state.B.Life > 0) return state;
        var winner = state.A.Life > 0 ? state.A.Player : state.B.Life > 0 ? state.B.Player : (PlayerId?)null;
        events.Add(new(state.Revision, state.ActionValue, "BattleFinished", winner ?? state.A.Player));
        return state with { Phase = CombatPhase.Finished, Winner = winner,
            DoubleKnockout = state.A.Life <= 0 && state.B.Life <= 0 };
    }

    private static CombatantState TryRewind(CombatantState state, int actionValue, List<CombatEvent> events, long revision)
    {
        var snapshot = state.RewindSnapshot;
        if (state.Life > 0 || snapshot is null || actionValue > snapshot.ExpiresAtActionValue) return state;
        var restored = state with
        {
            Life = snapshot.Life, Attack = snapshot.Attack, Defense = snapshot.Defense, Shield = snapshot.Shield,
            WindLayers = snapshot.WindLayers, WaterLayers = snapshot.WaterLayers, EarthLayers = snapshot.EarthLayers,
            FireLayers = snapshot.FireLayers, Embers = snapshot.Embers, EmberDamageActive = snapshot.EmberDamageActive,
            EarthBarrierActive = snapshot.EarthBarrierActive, ShieldBreakReturnPercent = snapshot.ShieldBreakReturnPercent,
            ShieldBreakReturnFlat = snapshot.ShieldBreakReturnFlat, AttackIntervalModifier = snapshot.AttackIntervalModifier,
            PermanentIntervalMultiplierPercent = snapshot.PermanentIntervalMultiplierPercent,
            WindTraceActive = snapshot.WindTraceActive, WindGaleActive = snapshot.WindGaleActive,
            WindArrowActive = snapshot.WindArrowActive, WindChaseActive = snapshot.WindChaseActive,
            TideActive = snapshot.TideActive, TideRefundPercent = snapshot.TideRefundPercent,
            PoisonLayers = 0, TemporaryAttackReduction = 0, TemporaryDefenseReduction = 0, TemporaryPoisonLayers = 0,
            BattleAttackReduction = 0, BattleDefenseReduction = 0, NegativeSuppressedUntilActionValue = 0,
            HealingReductionPercent = 0, HealingReductionUntilActionValue = 0,
            BattleIncomingDamageMultiplierPercent = 100, BattleIncomingDamageUntilActionValue = 0,
            NextIncomingDamageMultiplierPercent = 100, NextIncomingDamageFlat = 0,
            TemporaryShield = 0, Tides = 0m, NextTideHealingRecordBonusPercent = 0, NextDrawBonus = 0, NextEnergyBonus = 0, NextGapAdjustment = 0,
            PendingSubmissiles = 0, PendingWindSubmissiles = 0, NextMissileBonusPercent = 0, NextMissileBonusFlat = 0, NextMissileHealingPercent = 0,
            NextShieldPenetrationPercent = 0, MainShieldPenetrationUntilDrawPercent = 0, MainDefensePenetrationPercent = 0, NextDefensePenetrationPercent = 0, NextMainTemporaryShieldPercent = 0, NextWaterShieldHealingMultiplierPercent = 100,
            RewindSnapshot = null
            ,BastionHeartActive = snapshot.BastionHeartActive
            ,BurningBloodlineActive = snapshot.BurningBloodlineActive, LifeSpringActive = snapshot.LifeSpringActive
            ,ShieldDecay = new ShieldDecayState(Active: snapshot.ShieldDecayActive)
        };
        events.Add(new(revision, actionValue, "TimeRewind", restored.Player));
        return restored;
    }

    private static CombatantState GetPlayer(CombatState state, PlayerId player) =>
        player == state.A.Player ? state.A : player == state.B.Player ? state.B :
            throw new ArgumentException("Unknown participant.", nameof(player));
    private static CombatState SetPlayer(CombatState state, CombatantState player) =>
        player.Player == state.A.Player ? state with { A = player } : state with { B = player };
}






























































