using Magicians.Core.Common;
using Magicians.Core.Match;

namespace Magicians.Application;

public sealed record BattleResultAnnouncement(int Round, BattleId Battle, string Text)
{
    public static BattleResultAnnouncement Create(BattleResult result, MatchState state, IReadOnlyList<GameEvent> events)
    {
        string Name(PlayerId id) => state.Players[id].PublicInfo.DisplayName;
        string Loss(PlayerId id)
        {
            var change = events.OfType<TournamentLifeChangedEvent>().SingleOrDefault(e => e.Player == id);
            return change is null ? $"{Name(id)}不扣赛事生命" :
                $"{Name(id)}扣除{change.Damage}点赛事生命（{change.PreviousLife} → {change.NewLife}）";
        }
        var outcome = result.DoubleElimination ? $"{Name(result.PlayerA)}与{Name(result.PlayerB)}同时倒下" :
            $"{Name(result.Winner!.Value)}战胜了{Name(result.Winner == result.PlayerA ? result.PlayerB : result.PlayerA)}";
        var losses = result.DoubleElimination ? $"{Loss(result.PlayerA)}；{Loss(result.PlayerB)}" :
            Loss(result.Winner == result.PlayerA ? result.PlayerB : result.PlayerA);
        return new(state.Round, result.Battle, $"第{state.Round}轮 · {outcome}；{losses}。");
    }
}
