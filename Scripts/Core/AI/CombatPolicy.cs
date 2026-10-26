using Magicians.Core.Cards;
using Magicians.Core.Combat;
using Magicians.Core.Common;

namespace Magicians.Core.AI;

public sealed record PublicCombatantState(
    PlayerId Player,
    int Life,
    int Attack,
    int Defense,
    int Shield,
    int ActionValue,
    int WindLayers,
    int WaterLayers,
    int EarthLayers
);

public sealed record CombatObservation(
    BattleId Battle,
    long Revision,
    int ActionValue,
    PlayerId Player,
    CombatSelfObservation Self,
    PublicCombatantState Opponent
);

// Compatibility policy sees only its legal hand and immediate resources.
public sealed record CombatSelfObservation(int Life, int Energy, IReadOnlyList<CardInstance> CurrentPool);

public interface ICombatPolicy
{
    CombatAction Choose(CombatObservation observation);
}

public sealed class Slice1CombatPolicy : ICombatPolicy
{
    private readonly CardDatabase _cards;

    public Slice1CombatPolicy(CardDatabase cards) => _cards = cards;

    public CombatAction Choose(CombatObservation observation)
    {
        var cards = observation.Self.CurrentPool
            .Where(card => card is not null)
            .Select(card => (Card: card, Cost: _cards.Get(card.CardId).Cost))
            .Where(item => item.Cost <= observation.Self.Energy)
            .OrderByDescending(item => Score(item.Card.CardId, observation.Self.Life))
            .ThenBy(item => item.Card.InstanceId.Value, StringComparer.Ordinal)
            .ToList();

        foreach (var item in cards)
        {
            return new CombatAction(
                CombatActionKind.PlayCard,
                item.Card.InstanceId);
        }
        return new CombatAction(CombatActionKind.EndWindow);
    }

    private static int Score(string cardId, int life) => cardId switch
    {
        "护盾" or "石肤" when life < 500 => 120,
        "护盾" or "石肤" => 80,
        "攻击强化" or "利刃" => 100,
        "微风" => 90,
        "速读" or "鼓舞" => 70,
        "水滴" => life < 900 ? 75 : 45,
        "检索附魔" => 60,
        _ => 10
    };
}
