using Godot;
using Magicians.Core.AI;
using Magicians.Core.Cards;
using Magicians.Core.Combat;
using Magicians.Core.Common;
using Magicians.Core.Match;

namespace Magicians.Tests;

public partial class HeadlessScenarioRunner : Node
{
    public override void _Ready()
    {
        try
        {
            var cardsPath = ProjectSettings.GlobalizePath("res://releases/v1.0/cards.json");
            var poolPath = ProjectSettings.GlobalizePath("res://Data/slice1/slice1-card-pool.json");
            var scenarioPath = ProjectSettings.GlobalizePath("res://Data/slice1/scenario.json");
            var database = CardDatabase.LoadFromJson(cardsPath);
            if (OS.GetCmdlineUserArgs().Contains("--card-presentation-only", StringComparer.Ordinal))
            {
                CardPresentationRegression.Run(database, ProjectSettings.GlobalizePath("res://"));
                GetTree().Quit(0);
                return;
            }
            var pool = Slice1CardPool.Load(poolPath);
            var fullPool = Slice1CardPool.LoadFull(
                ProjectSettings.GlobalizePath("res://releases/deckbuilding-v1.0/pool-counts.json"),
                ProjectSettings.GlobalizePath("res://releases/deckbuilding-v1.0/economy.json"),
                database);
            var scenario = Slice1Scenario.Load(scenarioPath);
            if (database.Version != "1.0" || database.Count != 252)
                throw new InvalidDataException("Slice 1 requires frozen card data version 1.0 with 252 cards.");
            pool.ValidateAgainst(database);
            if (fullPool.SupportedCardIds.Count != 252 || fullPool.OfferPool.Sum(entry => entry.Count) != 1052 || fullPool.StarterCardsConsumePool)
                throw new InvalidDataException("Frozen all-card pool did not load the expected 252 cards and 1052 physical copies.");
            var effects = CardEffectRegistry.CreateSlice1(database);
            if (effects.All.Count != 252 || effects.ImplementedCardIds.Count != 252 || effects.UnsupportedCards.Count != 0)
                throw new InvalidDataException($"Card effect registry coverage mismatch: all={effects.All.Count}, implemented={effects.ImplementedCardIds.Count}, unsupported={effects.UnsupportedCards.Count}.");
            FullPoolActivationGuard.RequireAllEffectsImplemented(fullPool, effects);
            DraftAllocationRegression.Run(database, fullPool, ProjectSettings.GlobalizePath("res://"));

            CombatEffectRegression.Run(database);
            BastionHeartRegression.Run(database);
            CardExecutionAudit.Run(database, ProjectSettings.GlobalizePath("res://../runtime/card-effect-audit.json"));
            CardPresentationRegression.Run(database, ProjectSettings.GlobalizePath("res://"));
            DamageFormulaRegression.Run();
            EffectPipelineRegression.Run(database);
            AiPrivacyRegression.Run(ProjectSettings.GlobalizePath("res://"));
            FullTournamentRegression.Run(ProjectSettings.GlobalizePath("res://"));
            DraftRulesRegression.Run(database, pool, fullPool);
            var fixedSeedHash = FixedSeedRegression.Run(database, pool, scenario);

            var coordinator = new MatchCoordinator(database, pool);
            var state = coordinator.Start(new StartMatchSetup(
                new MatchId("headless-slice1"),
                Seed: 20261024,
                new[]
                {
                    new PlayerSetup(new PlayerId("human"), PlayerKind.Human, "Player"),
                    new PlayerSetup(new PlayerId("ai-1"), PlayerKind.Ai, "AI 1"),
                    new PlayerSetup(new PlayerId("ai-2"), PlayerKind.Ai, "AI 2"),
                    new PlayerSetup(new PlayerId("ai-3"), PlayerKind.Ai, "AI 3")
                },
                scenario.Round,
                scenario.InitialTournamentLife,
                scenario.InitialStudyPoints,
                scenario.OffersPerPlayer));

            if (state.Players.Count != 4 ||
                state.Players.Values.Any(player => player.Deck.Cards.Count != 8) ||
                state.Players.Values.Any(player => player.TournamentLife != scenario.InitialTournamentLife) ||
                state.Players.Values.Any(player => player.Draft.StudyPoints != scenario.InitialStudyPoints))
                throw new InvalidDataException("Slice 1 initialization did not create four 8-card decks.");

            var draftResult = coordinator.Submit(new BeginDraftCommand(
                state.Id,
                new PlayerId("human"),
                new CommandSequence(state.EventSequence + 1)));
            if (!draftResult.Accepted || draftResult.State.Phase != MatchPhase.Draft)
                throw new InvalidDataException("BeginDraftCommand was not accepted from setup phase.");
            var initialOfferInventory = state.SharedCardInventory.Values.Sum();
            var reservedOffers = coordinator.CurrentState.Players.Values
                .SelectMany(player => player.Draft.Offers)
                .Count(offer => !offer.IsResolved);
            if (coordinator.CurrentState.SharedCardInventory.Values.Sum() + reservedOffers != initialOfferInventory)
                throw new InvalidDataException("Offer inventory was not conserved after generation.");

            var aiControllers = new Dictionary<PlayerId, Slice1AiController>
            {
                [new PlayerId("ai-1")] = new(new Slice1DraftPolicy(reserveStudyPoints: 0, minimumScore: 60)),
                [new PlayerId("ai-2")] = new(new Slice1DraftPolicy(reserveStudyPoints: 1, minimumScore: 60)),
                [new PlayerId("ai-3")] = new(new Slice1DraftPolicy(reserveStudyPoints: 1, minimumScore: 85))
            };
            foreach (var playerId in coordinator.CurrentState.Players.Keys
                         .OrderBy(id => id.Value, StringComparer.Ordinal))
            {
                if (coordinator.CurrentState.Players[playerId].Kind == PlayerKind.Ai)
                {
                    aiControllers[playerId].CompleteDraft(coordinator, playerId);
                    continue;
                }
                var draftPlayer = coordinator.CurrentState.Players[playerId];
                var offer = draftPlayer.Draft.Offers.FirstOrDefault();
                if (offer is null)
                    throw new InvalidDataException($"No offer was generated for '{playerId}'.");

                var purchase = coordinator.Submit(new BuyCardCommand(
                    coordinator.CurrentState.Id,
                    playerId,
                    offer.SlotId,
                    new CommandSequence(coordinator.CurrentState.EventSequence + 1)));
                if (!purchase.Accepted)
                    throw new InvalidDataException($"Purchase failed for '{playerId}': {purchase.Rejection?.Message}");

                var duplicatePurchase = coordinator.Submit(new BuyCardCommand(
                    coordinator.CurrentState.Id,
                    playerId,
                    offer.SlotId,
                    new CommandSequence(coordinator.CurrentState.EventSequence + 1)));
                if (duplicatePurchase.Accepted || duplicatePurchase.Rejection?.Code != "OfferResolved")
                    throw new InvalidDataException("A resolved offer accepted a second purchase command.");

                var finish = coordinator.Submit(new FinishDraftCommand(
                    coordinator.CurrentState.Id,
                    playerId,
                    new CommandSequence(coordinator.CurrentState.EventSequence + 1)));
                if (!finish.Accepted)
                    throw new InvalidDataException($"Finish draft failed for '{playerId}': {finish.Rejection?.Message}");
            }

            var completedState = coordinator.CurrentState;
            if (completedState.Phase != MatchPhase.Combat ||
                completedState.Pairings.Count != 2 ||
                completedState.Players.Values.Any(player => player.Deck.Cards.Count < 9) ||
                completedState.Players.Values.Any(player => player.Kind == PlayerKind.Human && player.Draft.StudyPoints != 2) ||
                completedState.Players.Values.Any(player => player.Kind == PlayerKind.Ai && player.Draft.PurchasedCardIds.Count > 3) ||
                completedState.Players.Values.Where(player => player.Kind == PlayerKind.Ai).All(player => player.Draft.StudyPoints == 0) ||
                completedState.Players.Values.SelectMany(player => player.Draft.Offers).Any(offer => !offer.IsResolved) ||
                completedState.SharedCardInventory.Values.Sum() != initialOfferInventory -
                    completedState.Players.Values.Sum(player => player.Draft.PurchasedCardIds.Count))
                 throw new InvalidDataException($"Slice 1 draft did not complete: phase={completedState.Phase}, pairings={completedState.Pairings.Count}, players={string.Join(';', completedState.Players.Values.Select(p => p.Id.Value + ':' + p.Draft.StudyPoints + ':' + p.Draft.PurchasedCardIds.Count))}, inventory={completedState.SharedCardInventory.Values.Sum()}, initial={initialOfferInventory}.");

            var combat = new Slice1CombatEngine(database);
            var battleManager = BattleInstanceManager.Create(completedState, combat);
            if (battleManager.Instances.Count != 2)
                throw new InvalidDataException("Battle instance manager did not create one instance per pairing.");
            var battle = combat.Start(new CombatSetup(
                new BattleId("headless-battle"),
                new CombatantSetup(new PlayerId("human"), completedState.Players[new PlayerId("human")].Deck.Cards, 11),
                new CombatantSetup(new PlayerId("ai-1"), completedState.Players[new PlayerId("ai-1")].Deck.Cards, 12)));
            if (battle.A.CurrentPool.Count != 5 || battle.B.CurrentPool.Count != 5 || battle.A.Energy != 3 || battle.B.Energy != 3)
                throw new InvalidDataException("Combat did not create the initial five-card pools and three energy.");

            var firstA = ChooseAction(battle.A);
            var firstB = ChooseAction(battle.B);
            var first = combat.Submit(battle, new CombatCommand(
                battle.Battle, battle.A.Player, battle.Revision, firstA));
            var firstPair = combat.Submit(first.State, new CombatCommand(
                battle.Battle, battle.B.Player, battle.Revision, firstB));
            if (!first.Accepted || !firstPair.Accepted || firstPair.State.Revision != 1)
                throw new InvalidDataException("Synchronized combat actions did not resolve as one step.");

            var secondPlayA = combat.Submit(firstPair.State, new CombatCommand(
                battle.Battle, battle.A.Player, firstPair.State.Revision, ChooseAction(firstPair.State.A)));
            var secondPlayPair = combat.Submit(secondPlayA.State, new CombatCommand(
                battle.Battle, battle.B.Player, firstPair.State.Revision, ChooseAction(firstPair.State.B)));
            if (!secondPlayA.Accepted || !secondPlayPair.Accepted || secondPlayPair.State.Revision != 2 ||
                secondPlayPair.State.ActionValue != firstPair.State.ActionValue)
                throw new InvalidDataException("The combat queue did not accept a second synchronized card step.");

            var closeA = combat.Submit(secondPlayPair.State, new CombatCommand(
                battle.Battle, battle.A.Player, secondPlayPair.State.Revision, new CombatAction(CombatActionKind.EndWindow)));
            var closePair = combat.Submit(closeA.State, new CombatCommand(
                battle.Battle, battle.B.Player, secondPlayPair.State.Revision, new CombatAction(CombatActionKind.EndWindow)));
            var fireA = combat.Submit(closePair.State, new CombatCommand(
                battle.Battle, battle.A.Player, closePair.State.Revision, new CombatAction(CombatActionKind.EndWindow)));
            var firePair = combat.Submit(fireA.State, new CombatCommand(
                battle.Battle, battle.B.Player, closePair.State.Revision, new CombatAction(CombatActionKind.EndWindow)));
            if (!closeA.Accepted || !closePair.Accepted || !fireA.Accepted || !firePair.Accepted || firePair.State.Revision != 4 ||
                !firePair.Events.Any(gameEvent => gameEvent.Kind == "MainMissile"))
                throw new InvalidDataException($"Combat did not resolve the synchronized firing group: close={closePair.State.Revision}, fire={firePair.State.Revision}, events={string.Join(',', firePair.Events.Select(gameEvent => gameEvent.Kind))}, action={firePair.State.ActionValue}.");

            var firstPairing = completedState.Pairings[0];
            var secondPairing = completedState.Pairings[1];
            var firstSettlement = coordinator.ApplyBattleResult(new BattleResult(
                firstPairing.BattleId,
                firstPairing.PlayerA,
                firstPairing.PlayerB,
                firstPairing.PlayerA,
                800,
                false));
            var secondSettlement = coordinator.ApplyBattleResult(new BattleResult(
                secondPairing.BattleId,
                secondPairing.PlayerA,
                secondPairing.PlayerB,
                secondPairing.PlayerB,
                700,
                false));
            if (!firstSettlement.Accepted || !secondSettlement.Accepted ||
                coordinator.CurrentState.Phase != MatchPhase.Settlement ||
                coordinator.CurrentState.Players[firstPairing.PlayerB].TournamentLife >= 100 ||
                coordinator.CurrentState.Players[secondPairing.PlayerA].TournamentLife >= 100)
                throw new InvalidDataException("Tournament settlement did not apply v1.0 loss damage.");

            var advance = coordinator.Submit(new AdvanceSettlementCommand(
                coordinator.CurrentState.Id,
                new PlayerId("human"),
                new CommandSequence(coordinator.CurrentState.EventSequence + 1)));
            if (!advance.Accepted || coordinator.CurrentState.Phase != MatchPhase.Pairing ||
                coordinator.CurrentState.Round != scenario.Round + 1 ||
                coordinator.CurrentState.RoundHistory.Count != 1)
                throw new InvalidDataException("Settlement did not prepare the next pairing phase.");

            var nextDraft = coordinator.Submit(new BeginRoundDraftCommand(
                coordinator.CurrentState.Id,
                new PlayerId("human"),
                new CommandSequence(coordinator.CurrentState.EventSequence + 1)));
            if (!nextDraft.Accepted || coordinator.CurrentState.Phase != MatchPhase.Draft ||
                coordinator.CurrentState.Pairings.Count != 2 ||
                coordinator.CurrentState.Players.Values.Any(player => player.Draft.Round != scenario.Round + 1))
                throw new InvalidDataException("The next round did not enter draft with new pairings.");

            GD.Print($"SLICE1_TOURNAMENT_OK cards={database.Count} players={completedState.Players.Count} pairings={completedState.Pairings.Count} combatRevision={firePair.State.Revision} phase={coordinator.CurrentState.Phase} round={coordinator.CurrentState.Round} fixedSeedHash={fixedSeedHash}");
            GetTree().Quit(0);
        }
        catch (Exception exception)
        {
            GD.PrintErr($"SLICE1_DATA_FAILED {exception}");
            GetTree().Quit(1);
        }
    }

    private static CombatAction ChooseAction(CombatantState player)
    {
        var card = player.CurrentPool.FirstOrDefault(candidate => candidate.CardId != "检索附魔");
        return card is null
            ? new CombatAction(CombatActionKind.EndWindow)
            : new CombatAction(CombatActionKind.PlayCard, card.InstanceId);
    }
}












