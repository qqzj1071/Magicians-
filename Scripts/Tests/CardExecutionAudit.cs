using System.Text.Json;
using Magicians.Core.Cards;
using Magicians.Core.Combat;
using Magicians.Core.Common;

namespace Magicians.Tests;

public static class CardExecutionAudit
{
    public static void Run(CardDatabase database, string outputPath)
    {
        var rows = new List<object>();
        foreach (var definition in database.All.OrderBy(c => c.Name, StringComparer.Ordinal))
        {
            foreach (var enriched in new[] { false, true })
            {
                var a = new PlayerId("audit-a");
                var b = new PlayerId("audit-b");
                var card = new CardInstance(new CardInstanceId("audit:" + definition.Name), definition.Name, a);
                var engine = new Slice1CombatEngine(database);
                var state = engine.Start(new CombatSetup(new BattleId("audit:" + definition.Name),
                    new CombatantSetup(a, new[] { card }, 123),
                    new CombatantSetup(b, new[] { new CardInstance(new CardInstanceId("audit-enemy"), "护盾", b) }, 456)));
                if (enriched)
                {
                    var candidates = new[] { "护盾", "火星", "水滴", "毒甲", "小检索", "不坏壁垒", "生命洪流", "时光倒流", "岩核重压", "山崩" }
                        .Select((id, index) => new CardInstance(new CardInstanceId("audit-pile:" + index), id, a)).ToArray();
                    state = state with
                    {
                        A = state.A with { Life = 400, Shield = 120, Attack = 100, Defense = 30, Energy = 20,
                            EarthLayers = 5, FireLayers = 5, WaterLayers = 5, WindLayers = 5,
                            PoisonEnchantmentLayers = 5, PoisonLayers = 3, Embers = 3,
                            EmberDamageActive = true, FireSpecialized = true, TideActive = true, Tides = 20.5m,
                            EarthBarrierActive = true, UnredeemedEmbersSpent = 6, DrawPile = candidates },
                        B = state.B with { PoisonLayers = 4, Shield = 120, Defense = 20 }
                    };
                }
                var search = engine.GetSearchSession(state, a, card.InstanceId);
                var action = new CombatAction(CombatActionKind.PlayCard, card.InstanceId);
                if (search is not null)
                    action = search.MaximumSelections > 1
                        ? action with { SearchTargets = search.Candidates.Take(search.MaximumSelections).Select(c => c.InstanceId).ToArray() }
                        : action with { SearchTarget = search.Candidates.FirstOrDefault()?.InstanceId };
                var pending = engine.Submit(state, new CombatCommand(state.Battle, a, state.Revision, action));
                var result = engine.Submit(pending.State, new CombatCommand(state.Battle, b, state.Revision, new CombatAction(CombatActionKind.EndWindow)));
                if (!pending.Accepted || !result.Accepted || result.State.A.Energy < 0 || result.State.A.Shield < 0 ||
                    result.State.A.Life > 1000 || result.State.B.Shield < 0 ||
                    !result.Events.Any(e => e.Kind == "CardPlayed" && e.CardId == definition.Name))
                    throw new InvalidDataException($"Card audit failed: {definition.Name}, enriched={enriched}.");
                if (definition.Ability && !result.State.A.ExhaustedCards.Any(c => c.InstanceId == card.InstanceId))
                    throw new InvalidDataException("Ability did not leave battle deck: " + definition.Name);
                var allCards = result.State.A.DrawPile.Concat(result.State.A.DiscardPile).Concat(result.State.A.CurrentPool).Concat(result.State.A.ExhaustedCards).ToArray();
                if (allCards.Select(c => c.InstanceId).Distinct().Count() != allCards.Length)
                    throw new InvalidDataException("Card duplicated between piles: " + definition.Name);
            }
            rows.Add(new { Card = definition.Name,
                Pipeline = CombatCardExecution.HasPipeline(definition.Name), Deck = CombatCardExecution.Deck.Contains(definition.Name),
                BaseAndEnrichedCommandPaths = "passed", definition.Ability });
        }
        Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
        File.WriteAllText(outputPath, JsonSerializer.Serialize(new
        {
            Cards = rows.Count, Cases = rows.Count * 2,
            Scope = "Authority command execution, registration, energy/shield bounds, ability exhaustion and pile identity; targeted interaction tests run separately. This is not exhaustive proof of every possible combo.",
            Results = rows
        }, new JsonSerializerOptions { WriteIndented = true }));
        Godot.GD.Print($"CARD_EXECUTION_AUDIT_OK cards={rows.Count} cases={rows.Count * 2}");
    }
}
