using Magicians.Core.Cards;
using Magicians.Core.Common;
using Magicians.Core.Draft;

namespace Magicians.Core.Match;

public sealed class MatchCoordinator
{
    private readonly CardDatabase _cardDatabase;
    private readonly Slice1CardPool _cardPool;
    private readonly IPairingService _pairingService;
    private readonly ITournamentDamageCalculator _damageCalculator;
    private readonly CardEffectRegistry _effects;
    private MatchState? _state;
    private SeededRandom? _random;

    public MatchCoordinator(
        CardDatabase cardDatabase,
        Slice1CardPool cardPool,
        IPairingService? pairingService = null,
        ITournamentDamageCalculator? damageCalculator = null,
        CardEffectRegistry? effects = null)
    {
        _cardDatabase = cardDatabase;
        _cardPool = cardPool;
        _pairingService = pairingService ?? new FirstRoundPairingService();
        _damageCalculator = damageCalculator ?? new FrozenV1TournamentDamageCalculator();
        _effects = effects ?? CardEffectRegistry.CreateSlice1(cardDatabase);
        _cardPool.ValidateAgainst(_cardDatabase);
    }

    public MatchState CurrentState =>
        _state ?? throw new InvalidOperationException("The match has not started.");

    public static MatchCoordinator Restore(
        CardDatabase cardDatabase,
        Slice1CardPool cardPool,
        MatchState state)
    {
        var coordinator = new MatchCoordinator(cardDatabase, cardPool)
        {
            _state = state,
            _random = SeededRandom.FromState(state.RandomState)
        };
        return coordinator;
    }

    public MatchState Start(StartMatchSetup setup)
    {
        if (_state is not null)
            throw new InvalidOperationException("The match has already started.");
        ValidateSetup(setup);
        var totalOfferInventory = _cardPool.OfferPool.Sum(entry => entry.Count);
        if (setup.OffersPerPlayer > _cardPool.OfferPool.Count ||
            totalOfferInventory < setup.Players.Count * setup.OffersPerPlayer)
            throw new ArgumentException("The configured offer pool cannot provide every player's offers.", nameof(setup));

        _random = new SeededRandom(setup.Seed);
        var players = new Dictionary<PlayerId, PlayerState>();
        foreach (var playerSetup in setup.Players.OrderBy(player => player.Id.Value, StringComparer.Ordinal))
        {
            var deck = DeckState.CreateInitial(playerSetup.Id, _cardPool, _random);
            players.Add(playerSetup.Id, new PlayerState(
                playerSetup.Id,
                playerSetup.Kind,
                setup.InitialTournamentLife,
                deck,
                DraftState.Initial(setup.Round, setup.InitialStudyPoints),
                new PublicPlayerInfo(playerSetup.DisplayName)));
        }

        var inventory = _cardPool.OfferPool.ToDictionary(
            entry => entry.CardId,
            entry => entry.Count,
            StringComparer.Ordinal);
        var initialState = new MatchState(
            setup.Match,
            setup.Round,
            MatchPhase.Setup,
            setup.Seed,
            _random.State,
            setup.InitialStudyPoints,
            setup.OffersPerPlayer,
            setup.AllowRefresh,
            setup.AllowRemove,
            setup.AllowSpecialization,
            setup.AllowRouteSelection,
            EventSequence: 0,
            players,
            inventory,
            Array.Empty<Pairing>(),
            Array.Empty<BattleResult>(),
            Array.Empty<GameEvent>(),
            Array.Empty<Pairing>(),
            Array.Empty<RoundSummary>(),
            new Dictionary<PlayerId, int>(),
            new Dictionary<PlayerId, PlayerState>());

        var events = new List<GameEvent>();
        var nextSequence = 1L;
        events.Add(new MatchStartedEvent(
            setup.Match,
            initialState.Round,
            nextSequence++,
            string.Empty,
            setup.Seed,
            setup.Players.OrderBy(player => player.Id.Value, StringComparer.Ordinal)
                .Select(player => player.Id).ToArray()));
        foreach (var player in players.Values)
        {
            events.Add(new PlayerInitializedEvent(
                setup.Match,
                initialState.Round,
                nextSequence++,
                string.Empty,
                player.Id,
                player.Kind,
                player.TournamentLife,
                player.Deck.Cards.Count));
        }

        _state = AttachEvents(initialState with { EventSequence = nextSequence - 1 }, events);
        return _state;
    }

    public CommandResult<MatchState> Submit(IGameCommand command)
    {
        if (_state is null)
            return Reject(command, "MatchNotStarted", "The match has not started.");
        if (command.MatchId != _state.Id)
            return Reject(command, "WrongMatch", "The command belongs to another match.");
        if (command.ExpectedPhase != _state.Phase)
            return Reject(command, "WrongPhase", $"Expected {_state.Phase}, got {command.ExpectedPhase}.");
        if (command.Sequence.Value != _state.EventSequence + 1)
            return Reject(command, "InvalidSequence", "Command sequence is not the next expected sequence.");
        if (!_state.Players.ContainsKey(command.Issuer))
            return Reject(command, "UnknownPlayer", "The issuer is not a participant in this match.");

        return command switch
        {
            BeginDraftCommand beginDraft => BeginDraft(beginDraft),
            BeginRoundDraftCommand beginRoundDraft => BeginRoundDraft(beginRoundDraft),
            AdvanceSettlementCommand advanceSettlement => AdvanceSettlement(advanceSettlement),
            RefreshOffersCommand refreshOffers => RefreshOffers(refreshOffers),
            RemoveCardCommand removeCard => RemoveCard(removeCard),
            ChooseSpecializationCommand specialization => ChooseSpecialization(specialization),
            ChooseRouteCommand route => ChooseRoute(route),
            ReplaceRouteCommand replaceRoute => ReplaceRoute(replaceRoute),
            BuyCardCommand buyCard => BuyCard(buyCard),
            SkipOfferCommand skipOffer => SkipOffer(skipOffer),
            FinishDraftCommand finishDraft => FinishDraft(finishDraft),
            _ => Reject(command, "UnsupportedCommand", $"Unsupported command: {command.GetType().Name}.")
        };
    }

    private CommandResult<MatchState> BeginDraft(BeginDraftCommand command)
    {
        if (_random is null)
            return Reject(command, "RandomNotInitialized", "The match random source is not initialized.");

        var players = _state!.Players.ToDictionary(pair => pair.Key, pair => pair.Value);
        var inventory = _state.SharedCardInventory.ToDictionary(pair => pair.Key, pair => pair.Value, StringComparer.Ordinal);
        var events = new List<GameEvent>();
        var nextSequence = _state.EventSequence + 1;
        var pairings = _state.Pairings.Count == 0
            ? (_state.Phase == MatchPhase.Pairing
                ? _pairingService.CreateNextRound(_state.Players, _state.PairingHistory, _state.Round)
                : _pairingService.CreateFirstRound(_state.Players))
            : _state.Pairings;
        var draftStartedState = _state with { Phase = MatchPhase.Draft, Pairings = pairings };
        events.Add(new PairingsPublishedEvent(
            draftStartedState.Id,
            draftStartedState.Round,
            nextSequence++,
            string.Empty,
            pairings));
        events.Add(new DraftPhaseStartedEvent(
            draftStartedState.Id,
            draftStartedState.Round,
            nextSequence++,
            string.Empty,
            players.Keys.OrderBy(id => id.Value, StringComparer.Ordinal).ToArray()));

        var unseen = inventory.Where(p => _cardDatabase.Get(p.Key).Rarity == CardRarity.Legendary)
            .ToDictionary(p => p.Key, p => p.Value, StringComparer.Ordinal);
        if (_cardPool.DraftRules is { } rules)
        {
            // Roll both faces for everyone before reserving even one concrete card.
            var active = players.Values.Where(p => p.TournamentLife > 0).OrderBy(p => p.Id.Value, StringComparer.Ordinal).ToArray();
            foreach (var p in active)
                players[p.Id] = p with { Draft = p.Draft with {
                    FirstRarities = rules.Template(_state.Round, 0, _state.OffersPerPlayer, _random),
                    RefreshRarities = rules.Template(_state.Round, 1, _state.OffersPerPlayer, _random) } };
            active = active.Select(p => players[p.Id]).ToArray();
            var allocation = new DraftOfferAllocator(_cardDatabase, rules).Generate(active,
                active.ToDictionary(p => p.Id, p => p.Draft.FirstRarities.ToArray()), _state.Round, false, inventory, unseen, _random);
            foreach (var p in active)
            {
                var offers = allocation.Offers[p.Id];
                players[p.Id] = p with { Draft = p.Draft with { Offers = offers, ShownLegendaryIds = allocation.SeenNames[p.Id],
                    AllocationAudit = allocation.Audit.Where(a => a.StartsWith(p.Id.Value + ":", StringComparison.Ordinal)).ToArray() } };
                events.Add(new OffersGeneratedEvent(draftStartedState.Id, draftStartedState.Round, nextSequence++, string.Empty, p.Id, offers));
            }
        }
        else foreach (var player in players.Values.Where(player => player.TournamentLife > 0)
                     .OrderBy(player => player.Id.Value, StringComparer.Ordinal).ToArray())
        {
            var forceUnselectedRoute = player.Draft.Round is 8 or 10 or 12 && player.Draft.SpecializationElement is null;
            var offers = GenerateOffers(player, inventory, _random, _state.OffersPerPlayer, forceUnselectedRoute);
            players[player.Id] = player with { Draft = player.Draft with { Offers = offers } };
            events.Add(new OffersGeneratedEvent(
                draftStartedState.Id,
                draftStartedState.Round,
                nextSequence++,
                string.Empty,
                player.Id,
                offers));
        }

        var nextState = draftStartedState with
        {
            EventSequence = nextSequence - 1,
            RandomState = _random.State,
            Players = players,
            SharedCardInventory = inventory,
            UnseenLegendaryCopies = _cardPool.DraftRules is null ? _state.UnseenLegendaryCopies : unseen
        };
        _state = AttachEvents(nextState, events);
        return AcceptedResult(events.Count);
    }

    private CommandResult<MatchState> BuyCard(BuyCardCommand command)
    {
        var player = _state!.Players[command.Issuer];
        if (player.Draft.IsCompleted)
            return Reject(command, "DraftCompleted", "The player already completed this draft.");
        var offer = player.Draft.Offers.FirstOrDefault(slot => slot.SlotId == command.OfferSlotId);
        if (offer is null)
            return Reject(command, "OfferUnavailable", "The offer slot does not exist.");
        if (offer.IsResolved)
            return Reject(command, "OfferResolved", "The offer slot has already been resolved.");
        var definition = _cardDatabase.Get(offer.Card.CardId);
        if (!_effects.IsImplemented(offer.Card.CardId))
            return Reject(command, "UnsupportedInSlice1", $"Card effect is not implemented: {offer.Card.CardId}.");
        var freePurchase = !player.Draft.FreePurchaseUsed &&
            ((player.Draft.Round <= 2 && definition.Rarity == CardRarity.Common) ||
             (player.Draft.Round is >= 3 and <= 4 && definition.Rarity is CardRarity.Common or CardRarity.Rare));
        var replaced = command.ReplaceCard is { } replaceId ? player.Deck.Cards.FirstOrDefault(c => c.InstanceId == replaceId) : null;
        if (command.ReplaceCard is not null && replaced is null)
            return Reject(command, "ReplacementUnavailable", "The replacement card is not owned.");
        if (replaced is not null)
        {
            var old = _cardDatabase.Get(replaced.CardId);
            if (old.Rarity != CardRarity.Legendary || definition.Rarity != CardRarity.Legendary ||
                old.Kind == CardKind.RouteLegendary && (definition.Kind != CardKind.RouteLegendary || definition.Element != player.Draft.SpecializationElement))
                return Reject(command, "InvalidLegendaryReplacement", "Only legal legendary replacements are allowed.");
            if (player.Draft.SpecializationElement is { } main && MainElementCount(player, main, replaced.InstanceId) +
                (definition.Element == main && definition.Layers > 0 ? 1 : 0) < 3)
                return Reject(command, "SpecializationRequirement", "Replacement cannot reduce main-element cards below three.");
        }
        var effectiveCost = replaced is not null && _cardDatabase.Get(replaced.CardId).Kind == CardKind.RouteLegendary &&
            definition.Kind == CardKind.RouteLegendary ? 2 : freePurchase ? 0 : offer.Cost;
        if (effectiveCost > player.Draft.StudyPoints)
            return Reject(command, "InsufficientStudyPoints", "The player cannot afford this card.");
        if (player.Deck.Cards.Any(card => card.CardId == offer.Card.CardId))
            return Reject(command, "DuplicateCard", "The player already owns this card name.");
        if (player.Draft.SpecializationElement is { } specialized && definition.Element != "generic" && definition.Element != specialized)
            return Reject(command, "SpecializedElementRestriction", "A specialized player cannot buy a new foreign-element card.");
        if (definition.Rarity == CardRarity.Legendary && replaced is null && player.Deck.Cards.Count(c => _cardDatabase.Get(c.CardId).Rarity == CardRarity.Legendary) >= 3)
            return Reject(command, "LegendaryLimitReached", "Three legendary cards are already held.");
        if (definition.Kind == CardKind.RouteLegendary && player.Draft.RouteLegendaryId is not null && replaced?.CardId != player.Draft.RouteLegendaryId)
            return Reject(command, "RouteAlreadyOwned", "Replace the existing route explicitly.");

        var updatedOffers = player.Draft.Offers
            .Select(slot => slot.SlotId == offer.SlotId ? slot with { IsPurchased = true } : slot)
            .ToArray();
        var updatedDraft = player.Draft with
        {
            StudyPoints = player.Draft.StudyPoints - effectiveCost,
            FreePurchaseUsed = player.Draft.FreePurchaseUsed || freePurchase,
            Offers = updatedOffers,
            PurchasedCardIds = player.Draft.PurchasedCardIds.Append(offer.Card.CardId).ToArray()
            ,RouteLegendaryId = definition.Kind == CardKind.RouteLegendary ? definition.Name : player.Draft.RouteLegendaryId
        };
        var updatedDeck = player.Deck with { Cards = player.Deck.Cards.Where(c => c.InstanceId != replaced?.InstanceId).Append(offer.Card).ToArray() };
        CardDefinition? gifted = null;
        if (!_cardPool.StarterCardsConsumePool && _state.AllowSpecialization && updatedDraft.SpecializationElement is null &&
            definition.Layers > 0 && definition.Element != "generic" &&
            updatedDeck.Cards.Count(c => _cardDatabase.Get(c.CardId).Element == definition.Element && _cardDatabase.Get(c.CardId).Layers > 0) >= 3)
        {
            gifted = _cardDatabase.All.Single(c => c.Kind == CardKind.Specialization && c.Element == definition.Element);
            updatedDeck = updatedDeck with { Cards = updatedDeck.Cards.Append(new CardInstance(
                new CardInstanceId($"{player.Id.Value}:specialization:{definition.Element}"), gifted.Name, player.Id)).ToArray() };
            updatedDraft = updatedDraft with { SpecializationElement = definition.Element,
                PurchasedCardIds = updatedDraft.PurchasedCardIds.Append(gifted.Name).ToArray() };
        }
        var players = _state.Players.ToDictionary(pair => pair.Key, pair => pair.Value);
        players[player.Id] = player with { Deck = updatedDeck, Draft = updatedDraft };
        var nextSequence = _state.EventSequence + 1;
        var pendingReturns = _state.PendingPoolReturns.ToDictionary(p => p.Key, p => p.Value, StringComparer.Ordinal);
        if (replaced is not null) pendingReturns[replaced.CardId] = pendingReturns.GetValueOrDefault(replaced.CardId) + 1;
        var nextState = _state with { EventSequence = nextSequence, Players = players, PendingPoolReturns = pendingReturns };
        var gameEvent = new CardPurchasedEvent(
            nextState.Id,
            nextState.Round,
            nextSequence,
            string.Empty,
            player.Id,
            offer.Card.InstanceId,
            offer.SlotId,
            effectiveCost);
        var purchaseEvents = new List<GameEvent> { gameEvent };
        if (definition.Kind == CardKind.RouteLegendary)
            purchaseEvents.Add(new DraftRuleChangedEvent(nextState.Id, nextState.Round, ++nextSequence, string.Empty,
                player.Id, replaced is null ? "Route" : "ReplaceRoute", new[] { definition.Name }));
        if (gifted is not null)
            purchaseEvents.Add(new DraftRuleChangedEvent(nextState.Id, nextState.Round, ++nextSequence, string.Empty,
                player.Id, "Specialization", new[] { gifted.Name }));
        _state = AttachEvents(nextState with { EventSequence = nextSequence }, purchaseEvents);
        return AcceptedResult(purchaseEvents.Count);
    }

    private CommandResult<MatchState> SkipOffer(SkipOfferCommand command)
    {
        var player = _state!.Players[command.Issuer];
        var offer = player.Draft.Offers.FirstOrDefault(slot => slot.SlotId == command.OfferSlotId);
        if (player.Draft.IsCompleted)
            return Reject(command, "DraftCompleted", "The player already completed this draft.");
        if (offer is null)
            return Reject(command, "OfferUnavailable", "The offer slot does not exist.");
        if (offer.IsResolved)
            return Reject(command, "OfferResolved", "The offer slot has already been resolved.");

        var players = _state.Players.ToDictionary(pair => pair.Key, pair => pair.Value);
        var updatedOffers = player.Draft.Offers
            .Select(slot => slot.SlotId == offer.SlotId ? slot with { IsSkipped = true } : slot)
            .ToArray();
        players[player.Id] = player with { Draft = player.Draft with { Offers = updatedOffers } };
        var inventory = _state.SharedCardInventory.ToDictionary(pair => pair.Key, pair => pair.Value, StringComparer.Ordinal);
        inventory[offer.Card.CardId]++;
        var nextSequence = _state.EventSequence + 1;
        var nextState = _state with
        {
            EventSequence = nextSequence,
            Players = players,
            SharedCardInventory = inventory
        };
        var gameEvent = new OfferSkippedEvent(
            nextState.Id,
            nextState.Round,
            nextSequence,
            string.Empty,
            player.Id,
            offer.SlotId);
        _state = AttachEvents(nextState, new[] { gameEvent });
        return AcceptedResult(1);
    }

    private CommandResult<MatchState> RefreshOffers(RefreshOffersCommand command)
    {
        if (!_state!.AllowRefresh)
            return Reject(command, "RefreshDisabled", "Refreshing offers is disabled for this scenario.");
        if (_random is null)
            return Reject(command, "RandomNotInitialized", "The match random source is not initialized.");
        var player = _state.Players[command.Issuer];
        if (player.Draft.IsCompleted)
            return Reject(command, "DraftCompleted", "The player already completed this draft.");
        if (player.Draft.RefreshesUsed >= 1)
            return Reject(command, "RefreshLimitReached", "Only one refresh is allowed per round.");
        if (player.Draft.StudyPoints < 1)
            return Reject(command, "InsufficientStudyPoints", "Refreshing costs one study point.");

        if (_cardPool.DraftRules is { } rules)
        {
            if (player.Draft.Offers.Count(o => o.IsPurchased) >= _state.OffersPerPlayer)
                return Reject(command, "RefreshUnavailable", "There are no unpurchased slots.");
            var stock = _state.SharedCardInventory.ToDictionary(p => p.Key, p => p.Value, StringComparer.Ordinal);
            foreach (var old in player.Draft.Offers.Where(o => !o.IsResolved)) stock[old.Card.CardId]++;
            var unseen = _state.UnseenLegendaryCopies.ToDictionary(p => p.Key, p => p.Value, StringComparer.Ordinal);
            var transactionRandom = SeededRandom.FromState(_random.State);
            var allocation = new DraftOfferAllocator(_cardDatabase, rules).Generate(new[] { player },
                new Dictionary<PlayerId, int[]> { [player.Id] = player.Draft.RefreshRarities.ToArray() },
                _state.Round, true, stock, unseen, transactionRandom);
            var allocatedOffers = player.Draft.Offers.Where(o => o.IsPurchased).Concat(allocation.Offers[player.Id])
                .OrderBy(o => DraftOfferAllocator.Index(o.SlotId)).ToArray();
            var participants = _state.Players.ToDictionary(p => p.Key, p => p.Value);
            participants[player.Id] = player with { Draft = player.Draft with { StudyPoints = player.Draft.StudyPoints - 1,
                RefreshesUsed = 1, Offers = allocatedOffers, ShownLegendaryIds = allocation.SeenNames[player.Id],
                AllocationAudit = player.Draft.AllocationAudit.Concat(allocation.Audit).ToArray() } };
            var sequence = _state.EventSequence + 1;
            var updated = _state with { EventSequence = sequence, Players = participants, SharedCardInventory = stock,
                UnseenLegendaryCopies = unseen, RandomState = transactionRandom.State };
            _random = transactionRandom;
            _state = AttachEvents(updated, new[] { new DraftRuleChangedEvent(updated.Id, updated.Round, sequence, string.Empty,
                player.Id, "Refresh", allocatedOffers.Select(o => o.Card.CardId).ToArray()) });
            return AcceptedResult(1);
        }

        var unresolved = player.Draft.Offers.Where(offer => !offer.IsResolved).ToArray();
        var inventory = _state.SharedCardInventory.ToDictionary(pair => pair.Key, pair => pair.Value, StringComparer.Ordinal);
        foreach (var offer in unresolved)
            inventory[offer.Card.CardId] = inventory.GetValueOrDefault(offer.Card.CardId) + 1;

        var owned = player.Deck.Cards.Select(card => card.CardId).ToHashSet(StringComparer.Ordinal);
        var candidates = inventory.Where(pair => pair.Value > 0 && !owned.Contains(pair.Key))
            .Select(pair => pair.Key).ToArray();
        if (candidates.Length < unresolved.Length)
            return Reject(command, "RefreshUnavailable", "The shared pool cannot refill every unresolved slot.");

        var selected = new HashSet<string>(StringComparer.Ordinal);
        var refreshed = new Dictionary<string, OfferSlot>(StringComparer.Ordinal);
        foreach (var old in unresolved)
        {
            var available = candidates.Where(id => !selected.Contains(id) && inventory.GetValueOrDefault(id) > 0).ToArray();
            var cardId = available[_random.NextInt(0, available.Length)];
            selected.Add(cardId);
            inventory[cardId]--;
            var card = new CardInstance(
                new CardInstanceId($"{player.Id.Value}:offer:r{player.Draft.Round}:refresh:{old.SlotId}"),
                cardId,
                player.Id);
            refreshed[old.SlotId] = old with { Card = card, Cost = StudyCost(_cardDatabase.Get(cardId)), IsPurchased = false, IsSkipped = false };
        }

        var offers = player.Draft.Offers.Select(offer =>
            refreshed.TryGetValue(offer.SlotId, out var replacement) ? replacement : offer).ToArray();
        var players = _state.Players.ToDictionary(pair => pair.Key, pair => pair.Value);
        players[player.Id] = player with { Draft = player.Draft with
        {
            StudyPoints = player.Draft.StudyPoints - 1,
            RefreshesUsed = player.Draft.RefreshesUsed + 1,
            Offers = offers
        }};
        var nextSequence = _state.EventSequence + 1;
        var nextState = _state with { EventSequence = nextSequence, Players = players, SharedCardInventory = inventory };
        _state = AttachEvents(nextState, new[] { new DraftRuleChangedEvent(nextState.Id, nextState.Round, nextSequence, string.Empty, player.Id, "Refresh", offers.Select(offer => offer.Card.CardId).ToArray()) });
        return AcceptedResult(1);
    }

    private CommandResult<MatchState> RemoveCard(RemoveCardCommand command)
    {
        if (!_state!.AllowRemove)
            return Reject(command, "RemoveDisabled", "Removing cards is disabled for this scenario.");
        var player = _state.Players[command.Issuer];
        if (player.Draft.IsCompleted)
            return Reject(command, "DraftCompleted", "The player already completed this draft.");
        var limit = player.Draft.Round <= 3 ? 0 : player.Draft.Round <= 6 ? 1 : 2;
        if (player.Draft.RemovalCount >= limit)
            return Reject(command, "RemoveLimitReached", "The player has used all removals for this round.");
        var card = player.Deck.Cards.FirstOrDefault(candidate => candidate.InstanceId == command.Card);
        if (card is null)
            return Reject(command, "CardUnavailable", "The card instance is not in the player's deck.");
        var definition = _cardDatabase.Get(card.CardId);
        if (definition.Rarity == CardRarity.Legendary)
            return Reject(command, "ProtectedCard", "Legendary cards cannot be removed.");
        if (definition.Kind == CardKind.Specialization)
            return Reject(command, "ProtectedCard", "Specialization cards cannot be removed.");
        if (player.Deck.Cards.Count <= 8)
            return Reject(command, "MinimumDeckSize", "A deck cannot be reduced below eight cards.");
        if (player.Draft.SpecializationElement is { } element && definition.Element == element &&
            MainElementCount(player, element, card.InstanceId) < 3)
            return Reject(command, "SpecializationRequirement", "The main-element enchantment count cannot fall below three.");
        var cost = player.Draft.Round >= 7 && player.Draft.RemovalCount > 0 ? 1 : 0;
        if (player.Draft.StudyPoints < cost)
            return Reject(command, "InsufficientStudyPoints", "The player cannot afford this removal.");

        var players = _state.Players.ToDictionary(pair => pair.Key, pair => pair.Value);
        players[player.Id] = player with
        {
            Deck = player.Deck with { Cards = player.Deck.Cards.Where(candidate => candidate.InstanceId != card.InstanceId).ToArray() },
            Draft = player.Draft with { RemovalCount = player.Draft.RemovalCount + 1, StudyPoints = player.Draft.StudyPoints - cost }
        };
        var returns = _state.PendingPoolReturns.ToDictionary(pair => pair.Key, pair => pair.Value, StringComparer.Ordinal);
        if (_cardPool.StarterCardsConsumePool || !card.InstanceId.Value.Contains(":initial:", StringComparison.Ordinal))
            returns[card.CardId] = returns.GetValueOrDefault(card.CardId) + 1;
        var nextSequence = _state.EventSequence + 1;
        var nextState = _state with { EventSequence = nextSequence, Players = players, PendingPoolReturns = returns };
        _state = AttachEvents(nextState, new[] { new DraftRuleChangedEvent(nextState.Id, nextState.Round, nextSequence, string.Empty, player.Id, "Remove", new[] { card.CardId }) });
        return AcceptedResult(1);
    }

    private CommandResult<MatchState> ChooseSpecialization(ChooseSpecializationCommand command)
    {
        if (!_state!.AllowSpecialization)
            return Reject(command, "SpecializationDisabled", "Specialization is disabled for this scenario.");
        var player = _state.Players[command.Issuer];
        if (player.Draft.SpecializationElement is not null)
            return Reject(command, "AlreadySpecialized", "The player already has a specialization.");
        var ownedLayers = player.Deck.Cards.Where(card => _cardDatabase.Get(card.CardId).Element == command.Element && _cardDatabase.Get(card.CardId).Layers > 0).ToArray();
        if (ownedLayers.Length < 3)
            return Reject(command, "SpecializationRequirement", "Three same-element enchantments are required.");
        if (!_cardDatabase.TryGet(command.CardId, out var definition) || definition.Kind != CardKind.Specialization || definition.Element != command.Element)
            return Reject(command, "InvalidSpecialization", "The selected card is not a specialization card for this element.");
        var instance = new CardInstance(new CardInstanceId($"{player.Id.Value}:specialization:{command.Element}"), command.CardId, player.Id);
        var players = _state.Players.ToDictionary(pair => pair.Key, pair => pair.Value);
        players[player.Id] = player with
        {
            Deck = player.Deck with { Cards = player.Deck.Cards.Append(instance).ToArray() },
            Draft = player.Draft with { SpecializationElement = command.Element, PurchasedCardIds = player.Draft.PurchasedCardIds.Append(command.CardId).ToArray() }
        };
        var nextSequence = _state.EventSequence + 1;
        var nextState = _state with { EventSequence = nextSequence, Players = players };
        _state = AttachEvents(nextState, new[] { new DraftRuleChangedEvent(nextState.Id, nextState.Round, nextSequence, string.Empty, player.Id, "Specialization", new[] { command.CardId }) });
        return AcceptedResult(1);
    }

    private CommandResult<MatchState> ChooseRoute(ChooseRouteCommand command) =>
        AddRoute(command, null);

    private CommandResult<MatchState> ReplaceRoute(ReplaceRouteCommand command) =>
        AddRoute(command, command.OldCardId);

    private CommandResult<MatchState> AddRoute(IGameCommand command, string? oldRoute)
    {
        if (!_state!.AllowRouteSelection)
            return Reject(command, "RouteDisabled", "Route selection is disabled for this scenario.");
        var player = _state.Players[command.Issuer];
        var newCardId = command is ChooseRouteCommand choose ? choose.CardId : ((ReplaceRouteCommand)command).NewCardId;
        if (!_cardDatabase.TryGet(newCardId, out var definition) || definition.Kind != CardKind.RouteLegendary)
            return Reject(command, "InvalidRoute", "The selected card is not a route legendary.");
        if (player.Draft.SpecializationElement is not { } element || definition.Element != element)
            return Reject(command, "RouteRequiresSpecialization", "A route requires a matching specialization.");
        var old = oldRoute is null ? null : player.Deck.Cards.FirstOrDefault(card => card.CardId == oldRoute);
        if (_cardPool.DraftRules is not null)
        {
            var offered = player.Draft.Offers.FirstOrDefault(o => !o.IsResolved && o.Card.CardId == newCardId);
            if (offered is null) return Reject(command, "RouteNotOffered", "A route must be purchased from the current offers.");
            if (oldRoute is not null && (old is null || _cardDatabase.Get(old.CardId).Kind != CardKind.RouteLegendary))
                return Reject(command, "RouteUnavailable", "The route to replace is not owned.");
            return BuyCard(new BuyCardCommand(_state.Id, player.Id, offered.SlotId, command.Sequence) { ReplaceCard = old?.InstanceId });
        }
        if (oldRoute is not null && old is null)
            return Reject(command, "RouteUnavailable", "The route to replace is not in the deck.");
        if (oldRoute is null && player.Draft.RouteLegendaryId is not null)
            return Reject(command, "RouteAlreadyOwned", "Only one route legendary can be held.");
        if (oldRoute is null && player.Deck.Cards.Count(card => _cardDatabase.Get(card.CardId).Rarity == CardRarity.Legendary) >= 3)
            return Reject(command, "LegendaryLimitReached", "A player may hold at most three legendary cards.");
        if (player.Deck.Cards.Any(card => card.CardId == newCardId && card.InstanceId != old?.InstanceId))
            return Reject(command, "DuplicateCard", "The player already owns this card name.");
        var cost = oldRoute is null ? StudyCost(definition) : 2;
        if (player.Draft.StudyPoints < cost)
            return Reject(command, "InsufficientStudyPoints", "The player cannot afford this route choice.");
        var inventory = _state.SharedCardInventory.ToDictionary(pair => pair.Key, pair => pair.Value, StringComparer.Ordinal);
        if (inventory.GetValueOrDefault(newCardId) <= 0)
            return Reject(command, "RouteUnavailable", "The selected route is not available in the shared pool.");
        inventory[newCardId]--;
        var routeReturns = _state.PendingPoolReturns.ToDictionary(pair => pair.Key, pair => pair.Value, StringComparer.Ordinal);
        if (old is not null) routeReturns[old.CardId] = routeReturns.GetValueOrDefault(old.CardId) + 1;
        if (old is not null && player.Draft.SpecializationElement is { } specializedElement &&
            definition.Element == specializedElement &&
            MainElementCount(player, specializedElement, old.InstanceId) + (definition.Layers > 0 ? 1 : 0) < 3)
            return Reject(command, "SpecializationRequirement", "Route replacement cannot reduce the main-element enchantment count below three.");
        var instance = new CardInstance(new CardInstanceId($"{player.Id.Value}:route:{newCardId}"), newCardId, player.Id);
        var cards = player.Deck.Cards.Where(card => old is null || card.InstanceId != old.InstanceId).Append(instance).ToArray();
        var players = _state.Players.ToDictionary(pair => pair.Key, pair => pair.Value);
        players[player.Id] = player with
        {
            Deck = player.Deck with { Cards = cards },
            Draft = player.Draft with { RouteLegendaryId = newCardId, StudyPoints = player.Draft.StudyPoints - cost, PurchasedCardIds = player.Draft.PurchasedCardIds.Append(newCardId).ToArray() }
        };
        var nextSequence = _state.EventSequence + 1;
        var nextState = _state with { EventSequence = nextSequence, Players = players, SharedCardInventory = inventory, PendingPoolReturns = routeReturns };
        _state = AttachEvents(nextState, new[] { new DraftRuleChangedEvent(nextState.Id, nextState.Round, nextSequence, string.Empty, player.Id, oldRoute is null ? "Route" : "ReplaceRoute", new[] { newCardId }) });
        return AcceptedResult(1);
    }

    private int MainElementCount(PlayerState player, string element, CardInstanceId excluded) =>
        player.Deck.Cards.Count(card => card.InstanceId != excluded &&
            _cardDatabase.Get(card.CardId).Element == element &&
            _cardDatabase.Get(card.CardId).Kind != CardKind.Specialization &&
            _cardDatabase.Get(card.CardId).Layers > 0);

    private CommandResult<MatchState> FinishDraft(FinishDraftCommand command)
    {
        var player = _state!.Players[command.Issuer];
        if (player.Draft.IsCompleted)
            return Reject(command, "DraftCompleted", "The player already completed this draft.");

        var inventory = _state.SharedCardInventory.ToDictionary(pair => pair.Key, pair => pair.Value, StringComparer.Ordinal);
        foreach (var offer in player.Draft.Offers.Where(offer => !offer.IsResolved))
            inventory[offer.Card.CardId]++;

        var players = _state.Players.ToDictionary(pair => pair.Key, pair => pair.Value);
        players[player.Id] = player with
        {
            Draft = player.Draft with
            {
                Offers = player.Draft.Offers.Select(offer => offer.IsResolved ? offer : offer with { IsSkipped = true }).ToArray(),
                IsCompleted = true
            }
        };
        var completed = players.Values.Where(other => other.TournamentLife > 0).All(other => other.Draft.IsCompleted);
        var firstSequence = _state.EventSequence + 1;
        var eventCount = completed ? 2 : 1;
        var nextState = _state with
        {
            Phase = completed ? MatchPhase.Combat : MatchPhase.Draft,
            EventSequence = firstSequence + eventCount - 1,
            Players = players,
            SharedCardInventory = inventory
        };
        var events = new List<GameEvent>
        {
            new DraftCompletedEvent(
                nextState.Id,
                nextState.Round,
                firstSequence,
                string.Empty,
                player.Id,
                players[player.Id].Draft.StudyPoints)
        };
        if (completed)
        {
            events.Add(new DraftRoundCompletedEvent(
                nextState.Id,
                nextState.Round,
                firstSequence + 1,
                string.Empty,
                players.Keys.OrderBy(id => id.Value, StringComparer.Ordinal).ToArray()));
        }
        _state = AttachEvents(nextState, events);
        return AcceptedResult(events.Count);
    }

    public CommandResult<MatchState> ApplyBattleResult(BattleResult result)
    {
        if (_state is null)
            return new(false, EmptyState(new MatchId("unstarted")), Array.Empty<GameEvent>(),
                new Rejection("MatchNotStarted", "The match has not started."), string.Empty);
        if (_state.Phase != MatchPhase.Combat)
            return RejectExternal("WrongPhase", "Battle results require the combat phase.");
        var pairing = _state.Pairings.FirstOrDefault(pair => pair.BattleId == result.Battle);
        if (pairing is null || pairing.PlayerA != result.PlayerA || pairing.PlayerB != result.PlayerB)
            return RejectExternal("UnknownBattle", "The battle result does not match a published pairing.");
        if (_state.BattleResults.Any(previous => previous.Battle == result.Battle))
            return RejectExternal("DuplicateBattleResult", "The battle result was already applied.");

        var players = _state.Players.ToDictionary(pair => pair.Key, pair => pair.Value);
        var events = new List<GameEvent>();
        var nextSequence = _state.EventSequence + 1;
        if (result.DoubleElimination)
        {
            var loss = _damageCalculator.CalculateDoubleEliminationLoss(_state.Round);
            ApplyLoss(players, result.PlayerA, loss, _state.Id, _state.Round, events, ref nextSequence);
            ApplyLoss(players, result.PlayerB, loss, _state.Id, _state.Round, events, ref nextSequence);
        }
        else
        {
            if (result.Winner is null || (result.Winner != result.PlayerA && result.Winner != result.PlayerB))
                return RejectExternal("InvalidWinner", "A non-double battle must have one of its participants as winner.");
            var loser = result.Winner == result.PlayerA ? result.PlayerB : result.PlayerA;
            var loss = _damageCalculator.CalculateLoss(_state.Round, result.WinnerRemainingCombatLife);
            ApplyLoss(players, loser, loss, _state.Id, _state.Round, events, ref nextSequence);
        }

        var results = _state.BattleResults.Append(result).ToArray();
        var finished = results.Length == _state.Pairings.Count;
        var nextState = _state with
        {
            Phase = finished ? MatchPhase.Settlement : MatchPhase.Combat,
            EventSequence = nextSequence - 1,
            Players = players,
            BattleResults = results
        };
        if (finished)
        {
            events.Add(new RoundFinishedEvent(
                nextState.Id,
                nextState.Round,
                nextSequence++,
                string.Empty,
                players.Values.Where(player => player.TournamentLife > 0)
                    .Select(player => player.Id).OrderBy(id => id.Value, StringComparer.Ordinal).ToArray()));
            events.Add(new SettlementStartedEvent(
                nextState.Id,
                nextState.Round,
                nextSequence++,
                string.Empty,
                players.Values.Where(player => player.TournamentLife > 0)
                    .Select(player => player.Id).OrderBy(id => id.Value, StringComparer.Ordinal).ToArray()));
            nextState = nextState with { EventSequence = nextSequence - 1 };
        }
        _state = AttachEvents(nextState, events);
        return new(true, _state, _state.EventLog.TakeLast(events.Count).ToArray(), null, StateHasher.Hash(_state));
    }

    private CommandResult<MatchState> BeginRoundDraft(BeginRoundDraftCommand command) => BeginDraft(
        new BeginDraftCommand(command.MatchId, command.Issuer, command.Sequence));

    private CommandResult<MatchState> AdvanceSettlement(AdvanceSettlementCommand command)
    {
        var survivors = _state!.Players.Values
            .Where(player => player.TournamentLife > 0)
            .Select(player => player.Id)
            .OrderBy(id => id.Value, StringComparer.Ordinal)
            .ToArray();
        var roundSummary = new RoundSummary(_state.Round, _state.Pairings, _state.BattleResults, survivors);
        var roundHistory = _state.RoundHistory.Append(roundSummary).ToArray();
        var pairHistory = _state.PairingHistory.Concat(_state.Pairings).ToArray();
        var firstSequence = _state.EventSequence + 1;
        var players = _state.Players.ToDictionary(pair => pair.Key, pair => pair.Value);
        foreach (var result in _state.BattleResults)
        {
            if (result.DoubleElimination || result.Winner is null)
            {
                if (players.TryGetValue(result.PlayerA, out var a)) players[result.PlayerA] = a with { WinStreak = 0, LossStreak = 0 };
                if (players.TryGetValue(result.PlayerB, out var b)) players[result.PlayerB] = b with { WinStreak = 0, LossStreak = 0 };
                continue;
            }

            var winnerId = result.Winner.Value;
            var winner = players[winnerId];
            var loserId = winnerId == result.PlayerA ? result.PlayerB : result.PlayerA;
            var loser = players[loserId];
            players[winnerId] = winner with { WinStreak = winner.WinStreak + 1, LossStreak = 0 };
            players[loserId] = loser with { WinStreak = 0, LossStreak = loser.LossStreak + 1 };
        }

        if (survivors.Length <= 1)
        {
            var finished = _state with
            {
                Phase = MatchPhase.Finished,
                EventSequence = firstSequence,
                PairingHistory = pairHistory,
                RoundHistory = roundHistory,
                Players = players
            };
            var championEvent = new TournamentFinishedEvent(
                finished.Id,
                finished.Round,
                firstSequence,
                string.Empty,
                TournamentStandings.Champions(finished));
            _state = AttachEvents(finished, new[] { championEvent });
            return AcceptedResult(1);
        }

        var nextRound = _state.Round + 1;
        var nextBaseStudy = nextRound <= 3 ? 2 : nextRound <= 7 ? 3 : 4;
        var nextStudy = survivors.ToDictionary(id => id, id =>
        {
            var player = players[id];
            var carry = Math.Min(2, player.Draft.StudyPoints);
            var streakBonus = player.WinStreak > 0 && player.WinStreak % 3 == 0 ||
                              player.LossStreak > 0 && player.LossStreak % 3 == 0 ? 1 : 0;
            return nextBaseStudy + carry + streakBonus;
        }, EqualityComparer<PlayerId>.Default);
        var ghosts = _state.GhostSnapshots.ToDictionary(pair => pair.Key, pair => pair.Value);
        var inventory = _state.SharedCardInventory.ToDictionary(pair => pair.Key, pair => pair.Value, StringComparer.Ordinal);
        foreach (var returned in _state.PendingPoolReturns) inventory[returned.Key] = inventory.GetValueOrDefault(returned.Key) + returned.Value;
        foreach (var player in players.Values.ToArray())
        {
            if (player.TournamentLife <= 0)
            {
                if (player.Kind == PlayerKind.Ghost) continue;
                foreach (var card in player.Deck.Cards)
                {
                    if (!_cardPool.StarterCardsConsumePool && (card.InstanceId.Value.Contains(":initial:", StringComparison.Ordinal) ||
                        card.InstanceId.Value.Contains(":specialization:", StringComparison.Ordinal))) continue;
                    inventory[card.CardId] = inventory.GetValueOrDefault(card.CardId) + 1;
                }
                players[player.Id] = player with
                {
                    Kind = PlayerKind.Ghost,
                    EliminatedRound = _state.Round,
                    PublicInfo = player.PublicInfo with { IsEliminated = true }
                };
                ghosts[player.Id] = players[player.Id];
                continue;
            }

            players[player.Id] = player with
            {
                Draft = DraftState.Initial(nextRound, nextStudy[player.Id]) with
                {
                    Offers = Array.Empty<OfferSlot>(),
                    SpecializationElement = player.Draft.SpecializationElement,
                    RouteLegendaryId = player.Draft.RouteLegendaryId,
                    PurchasedCardIds = player.Deck.Cards.Select(card => card.CardId).Distinct(StringComparer.Ordinal).ToArray()
                }
            };
        }

        var nextState = _state with
        {
            Phase = MatchPhase.Pairing,
            Round = nextRound,
            EventSequence = firstSequence,
            Players = players,
            Pairings = Array.Empty<Pairing>(),
            BattleResults = Array.Empty<BattleResult>(),
            PairingHistory = pairHistory,
            RoundHistory = roundHistory,
            NextRoundStudyPoints = nextStudy,
            GhostSnapshots = ghosts,
            SharedCardInventory = inventory
            ,PendingPoolReturns = new Dictionary<string, int>(StringComparer.Ordinal)
        };
        var nextRoundEvent = new NextRoundPreparedEvent(
            nextState.Id,
            nextRound,
            firstSequence,
            string.Empty,
            survivors);
        _state = AttachEvents(nextState, new[] { nextRoundEvent });
        return AcceptedResult(1);
    }

    private IReadOnlyList<OfferSlot> GenerateOffers(
        PlayerState player,
        IDictionary<string, int> inventory,
        IDeterministicRandom random,
        int offersPerPlayer,
        bool forceUnselectedRoute)
    {
        var owned = player.Deck.Cards.Select(card => card.CardId).ToHashSet(StringComparer.Ordinal);
        var selected = new HashSet<string>(StringComparer.Ordinal);
        var offers = new List<OfferSlot>();
        for (var index = 0; index < offersPerPlayer; index++)
        {
            var candidates = inventory
                .Where(pair => pair.Value > 0 && !owned.Contains(pair.Key) && !selected.Contains(pair.Key))
                .Select(pair => pair.Key)
                .ToList();
            if (candidates.Count == 0)
                break;
            if (index == 0 && forceUnselectedRoute)
            {
                var routeCandidates = candidates
                    .Where(cardId => _cardDatabase.Get(cardId).Kind == CardKind.RouteLegendary)
                    .ToList();
                if (routeCandidates.Count > 0)
                    candidates = routeCandidates;
            }
            var cardId = candidates[random.NextInt(0, candidates.Count)];
            selected.Add(cardId);
            inventory[cardId]--;
            var instanceId = new CardInstanceId(player.Draft.Round == 1
                ? $"{player.Id.Value}:offer:{index:D2}"
                : $"{player.Id.Value}:offer:r{player.Draft.Round}:{index:D2}");
            var card = new CardInstance(instanceId, cardId, player.Id);
            offers.Add(new OfferSlot(
                $"{player.Id.Value}:r{player.Draft.Round}:offer:{index:D2}",
                card,
                StudyCost(_cardDatabase.Get(cardId))));
        }
        return offers;
    }

    private int StudyCost(CardDefinition definition) => _cardPool.StarterCardsConsumePool ? definition.Cost : definition.Rarity switch
    {
        CardRarity.Common => 1,
        CardRarity.Rare => 2,
        CardRarity.Epic => 3,
        CardRarity.Legendary => 4,
        _ => 0
    };

    private CommandResult<MatchState> AcceptedResult(int eventCount)
    {
        var events = _state!.EventLog.TakeLast(eventCount).ToArray();
        return new CommandResult<MatchState>(true, _state, events, null, StateHasher.Hash(_state));
    }

    private CommandResult<MatchState> RejectExternal(string code, string message) => new(
        false,
        CurrentState,
        Array.Empty<GameEvent>(),
        new Rejection(code, message),
        StateHasher.Hash(CurrentState));

    private static void ApplyLoss(
        IDictionary<PlayerId, PlayerState> players,
        PlayerId playerId,
        int loss,
        MatchId matchId,
        int round,
        ICollection<GameEvent> events,
        ref long nextSequence)
    {
        var player = players[playerId];
        if (player.Kind == PlayerKind.Ghost)
            return;
        var nextLife = player.TournamentLife - loss;
        players[playerId] = player with
        {
            TournamentLife = nextLife,
            EliminatedRound = nextLife <= 0 ? player.EliminatedRound ?? round : null,
            PublicInfo = player.PublicInfo with { IsEliminated = nextLife <= 0 }
        };
        events.Add(new TournamentLifeChangedEvent(
            matchId,
            round,
            nextSequence++,
            string.Empty,
            playerId,
            player.TournamentLife,
            nextLife,
            loss));
    }

    private CommandResult<MatchState> Reject(IGameCommand command, string code, string message)
    {
        var state = _state ?? EmptyState(command.MatchId);
        return new CommandResult<MatchState>(
            false,
            state,
            Array.Empty<GameEvent>(),
            new Rejection(code, message),
            StateHasher.Hash(state));
    }

    private static MatchState AttachEvents(MatchState state, IReadOnlyList<GameEvent> events)
    {
        var hash = StateHasher.Hash(state);
        var finalized = events.Select(gameEvent => gameEvent with { StateHash = hash }).ToArray();
        return state with { EventLog = state.EventLog.Concat(finalized).ToArray() };
    }

    private static MatchState EmptyState(MatchId matchId) => new(
        matchId,
        0,
        MatchPhase.Setup,
        0,
        0,
        0,
        4,
        false,
        false,
        false,
        false,
        0,
        new Dictionary<PlayerId, PlayerState>(),
        new Dictionary<string, int>(),
        Array.Empty<Pairing>(),
        Array.Empty<BattleResult>(),
        Array.Empty<GameEvent>(),
        Array.Empty<Pairing>(),
        Array.Empty<RoundSummary>(),
        new Dictionary<PlayerId, int>(),
        new Dictionary<PlayerId, PlayerState>());

    private static void ValidateSetup(StartMatchSetup setup)
    {
        if (setup.Players.Count != 4)
            throw new ArgumentException("Slice 1 requires exactly four players.", nameof(setup));
        if (setup.Players.Count(player => player.Kind == PlayerKind.Human) != 1)
            throw new ArgumentException("Slice 1 requires exactly one human player.", nameof(setup));
        if (setup.Players.Count(player => player.Kind == PlayerKind.Ai) != 3)
            throw new ArgumentException("Slice 1 requires exactly three AI players.", nameof(setup));
        if (setup.Players.Select(player => player.Id).Distinct().Count() != 4)
            throw new ArgumentException("Player IDs must be unique.", nameof(setup));
        if (string.IsNullOrWhiteSpace(setup.Match.Value))
            throw new ArgumentException("Match ID is required.", nameof(setup));
        if (setup.InitialTournamentLife <= 0)
            throw new ArgumentException("Initial tournament life must be positive.", nameof(setup));
        if (setup.Round <= 0)
            throw new ArgumentException("Round must be positive.", nameof(setup));
        if (setup.InitialStudyPoints < 0)
            throw new ArgumentException("Initial study points cannot be negative.", nameof(setup));
        if (setup.OffersPerPlayer <= 0)
            throw new ArgumentException("Offers per player must be positive.", nameof(setup));
        if (setup.Players.Any(player => string.IsNullOrWhiteSpace(player.Id.Value)))
            throw new ArgumentException("Player IDs cannot be empty.", nameof(setup));
    }
}

