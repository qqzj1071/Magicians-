using System.Text.Json;
using Magicians.Application;
using Magicians.Core.AI;
using Magicians.Core.Cards;
using Magicians.Core.Combat;
using Magicians.Core.Common;
using Magicians.Core.Match;

namespace Magicians.Tests;

public static class AiPrivacyRegression
{
    private static readonly string[] Forbidden = { "RandomState", "DrawPile", "PendingActions", "GhostSnapshots", "SharedCardInventory", "NextRoundStudyPoints", "ElementForgePotentialLayers", "DeckElementCount" };
    public static void Run(string root)
    {
        using var session = GameSession.CreateSlice1(root);
        session.BeginDraft();
        var state = session.Coordinator.CurrentState;
        var player = new PlayerId("ai-1");
        var enemy = new PlayerId("human");
        var firstDraft = AiObservations.Draft(state, player, session.Cards);
        var changedPlayers = state.Players.ToDictionary(p => p.Key, p => p.Value);
        var hidden = changedPlayers[enemy];
        changedPlayers[enemy] = hidden with
        {
            Deck = hidden.Deck with { Cards = hidden.Deck.Cards.Select(c => c with { CardId = "时光倒流" }).ToArray(), DrawPile = hidden.Deck.DrawPile.Reverse().ToArray() },
            Draft = hidden.Draft with { StudyPoints = 999, Offers = hidden.Draft.Offers.Reverse().ToArray() }
        };
        var changed = state with { Seed = -111, RandomState = 999, Players = changedPlayers,
            SharedCardInventory = state.SharedCardInventory.ToDictionary(p => p.Key, p => p.Value * 10) };
        var secondDraft = AiObservations.Draft(changed, player, session.Cards);
        if (AiObservations.Hash(firstDraft) != AiObservations.Hash(secondDraft))
            throw new InvalidDataException("Hidden tournament data changed the draft observation.");
        var publicPlayers = state.Players.ToDictionary(p => p.Key, p => p.Value);
        publicPlayers[enemy] = publicPlayers[enemy] with { TournamentLife = 77 };
        if (AiObservations.Hash(firstDraft) == AiObservations.Hash(AiObservations.Draft(state with { Players = publicPlayers }, player, session.Cards)))
            throw new InvalidDataException("Public tournament health must remain visible to the draft actor.");
        var actionA = session.Ai.ChooseDraft(firstDraft);
        var actionB = session.Ai.ChooseDraft(secondDraft);
        if (actionA != actionB) throw new InvalidDataException("Hidden tournament data changed a trained draft action.");

        var a = state.Players[player];
        var b = state.Players[enemy];
        var engine = new Slice1CombatEngine(session.Cards);
        var combat = engine.Start(new CombatSetup(new BattleId("privacy"),
            new CombatantSetup(player, a.Deck.Cards, 10), new CombatantSetup(enemy, b.Deck.Cards, 20)));
        var instance = new BattleInstance(new Pairing(combat.Battle, player, enemy), combat,
            DeckSnapshot.Create(player, 1, a.Deck.Cards), DeckSnapshot.Create(enemy, 1, b.Deck.Cards), 10, 20);
        var first = AiObservations.Combat(state, instance, player);
        var mutated = instance with
        {
            SeedA = 999, SeedB = 888,
            SnapshotB = DeckSnapshot.Create(enemy, 1, changedPlayers[enemy].Deck.Cards),
            State = combat with
            {
                A = combat.A with { RandomState = 991, DrawPile = combat.A.DrawPile.Reverse().ToArray() },
                B = combat.B with { RandomState = 992, DrawPile = changedPlayers[enemy].Deck.Cards,
                    CurrentPool = Array.Empty<CardInstance>(), DeckElementCount = 99, ElementForgePotentialLayers = 99 },
                PendingActions = new[] { new PendingAction(enemy, new CombatAction(CombatActionKind.EndWindow)) }
            }
        };
        var second = AiObservations.Combat(changed, mutated, player);
        if (AiObservations.Hash(first) != AiObservations.Hash(second))
            throw new InvalidDataException("Hidden battle data changed the combat observation.");
        if (AiObservations.Hash(first) == AiObservations.Hash(AiObservations.Combat(state,
            instance with { State = combat with { B = combat.B with { Attack = combat.B.Attack + 5 } } }, player)))
            throw new InvalidDataException("Public opponent attack must remain visible to the combat actor.");
        if (session.Ai.ChooseCombat(first) != session.Ai.ChooseCombat(second))
            throw new InvalidDataException("Hidden battle data changed a trained combat action.");
        session.Ai.ChooseDraft(AiObservations.Draft(state, new PlayerId("ai-2"), session.Cards));
        if (session.Ai.WorkerCount != 2 || session.Ai.ChooseDraft(firstDraft) != actionA)
            throw new InvalidDataException("AI participants must have isolated workers and unchanged decisions after another participant's request.");
        AssertNoHiddenKeys(firstDraft);
        AssertNoHiddenKeys(first);
        if (JsonSerializer.Serialize(first, AiObservations.Json).Contains("searchCandidates", StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Search candidates were exposed before selecting a search card.");
        Godot.GD.Print("AI_PUBLIC_BOUNDARY_OK hidden-mutation-observations-and-decisions-equal");
    }

    private static void AssertNoHiddenKeys(object value)
    {
        using var doc = JsonDocument.Parse(JsonSerializer.Serialize(value, AiObservations.Json));
        void Visit(JsonElement element)
        {
            if (element.ValueKind == JsonValueKind.Object)
                foreach (var property in element.EnumerateObject())
                {
                    if (Forbidden.Contains(property.Name, StringComparer.OrdinalIgnoreCase))
                        throw new InvalidDataException("Private key crossed AI boundary: " + property.Name);
                    Visit(property.Value);
                }
            else if (element.ValueKind == JsonValueKind.Array) foreach (var child in element.EnumerateArray()) Visit(child);
        }
        Visit(doc.RootElement);
    }
}
