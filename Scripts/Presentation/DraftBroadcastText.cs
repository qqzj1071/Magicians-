using Magicians.Core.Cards;
using Magicians.Core.Common;
using Magicians.Core.Match;

namespace Magicians.Presentation;

public static class DraftBroadcastText
{
    public static IEnumerable<string> Lines(MatchState state, CardDatabase cards) => state.EventLog.OfType<DraftRuleChangedEvent>()
        .Where(e => e.Action is "Specialization" or "Route" or "ReplaceRoute")
        .GroupBy(e => e.Round).OrderBy(g => g.Key).Select(g =>
        {
            var entries = g.Select(e =>
            {
                var names = string.Join("、", e.CardIds);
                var action = e.Action == "Specialization" ? $"确定{CardPresentationCatalog.ElementLabel(cards.Get(e.CardIds[0]).Element)}系专精【{names}】" :
                    e.Action == "ReplaceRoute" ? $"替换传奇路线为【{names}】" : $"选择传奇路线【{names}】";
                return $"{state.Players[e.Player].PublicInfo.DisplayName}{action}";
            });
            return $"第{g.Key}轮 · " + string.Join("；", entries);
        });
}
