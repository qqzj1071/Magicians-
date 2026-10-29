using Magicians.Core.Combat;
using Magicians.Core.Common;

namespace Magicians.Presentation;

public static class CombatLogText
{
    public static string Missiles(IEnumerable<CombatEvent> events, PlayerId viewer) => string.Join("\n",
        events.Select(e => MissileLine(e, viewer)).Where(line => line is not null));

    private static string? MissileLine(CombatEvent e, PlayerId viewer)
    {
        var source = e.Player == viewer ? "你" : "对手";
        var target = e.Player == viewer ? "对手" : "你";
        var kind = e.Kind switch
        {
            "MainMissile" => "主弹", "Submissile" => "副弹", "WindSubmissile" => "风系副弹",
            "WindGaleTrueShot" => "疾风真伤副弹", "WindTraceExplosion" => "风痕引爆", "EarthReflect" => "护盾反击",
            _ => null
        };
        if (kind is not null)
            return $"[行动值{e.ActionValue}] {source} → {target} · {kind}结算：护盾损失{e.ShieldDamage}，生命损失{e.LifeDamage}";
        var effect = e.Kind switch
        {
            "EmberSpent" => $"主弹消耗余烬{e.Amount}层",
            "TideSpent" => $"主弹消耗潮汐{e.Amount}点",
            "ConditionalMissileHealing" => $"飞弹命中回复生命{e.Amount}点",
            "PoisonApplied" => "飞弹命中附毒",
            "ShieldBreakReturn" => $"破盾反应获得护盾{e.Amount}点",
            _ => null
        };
        return effect is null ? null : $"[行动值{e.ActionValue}] {source} · {effect}";
    }

    // Damage/poison/fatigue events must not push the paired played-card names
    // out of the log before the player can read them.
    public static string Exchanges(IEnumerable<CombatEvent> events, PlayerId viewer) => string.Join("\n",
        events.Where(e => e.Kind == "CardPlayed").GroupBy(e => e.Revision).TakeLast(3).Select(step =>
        {
            var own = step.Where(e => e.Player == viewer).Select(e => $"【{e.CardId}】").ToArray();
            var enemy = step.Where(e => e.Player != viewer).Select(e => $"【{e.CardId}】").ToArray();
            return $"[行动值{step.First().ActionValue}] 你：{(own.Length == 0 ? "本步未出牌" : string.Join("、", own))}；对手AI：{(enemy.Length == 0 ? "本步未出牌" : string.Join("、", enemy))}";
        }));
}
