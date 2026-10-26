namespace Magicians.Core.Combat;

public sealed record LegendaryAbilityStatusDefinition(
    string CardId,
    string StatusId,
    string ActivationCardId,
    string Description);

/// <summary>Stable IDs for legendary ability states. Effects can evolve without
/// coupling their lifetime to a card instance or display name.</summary>
public static class LegendaryAbilityStatusRegistry
{
    private static readonly IReadOnlyDictionary<string, LegendaryAbilityStatusDefinition> Definitions =
        new Dictionary<string, LegendaryAbilityStatusDefinition>(StringComparer.Ordinal)
        {
            ["炽焰王冠"] = new("炽焰王冠", "legendary.fire.ember_crown", "炽焰王冠", "余烬主弹倍率与抽牌阶段余烬"),
            ["潮汐回响"] = new("潮汐回响", "legendary.water.tide_echo", "潮汐回响", "潮汐记录倍率与发射返还"),
            ["穿云箭"] = new("穿云箭", "legendary.wind.piercing_arrow", "穿云箭", "风层防御/护盾穿透与护盾伤害"),
            ["风痕"] = new("风痕", "legendary.wind.trace", "风痕", "风痕叠层与引爆"),
            ["疾风之刃"] = new("疾风之刃", "legendary.wind.chasing_blade", "疾风之刃", "上一发主弹追击"),
            ["反震岩核"] = new("反震岩核", "legendary.earth.counter_core", "反震岩核", "碎盾反伤与返盾"),
            ["壁垒之心"] = new("壁垒之心", "legendary.earth.bastion_heart", "壁垒之心", "护盾反应与碎盾结算"),
            ["大地之握"] = new("大地之握", "legendary.earth.decay_grasp", "大地之握", "普通叠盾衰减转主弹伤害与碎盾穿盾"),
            ["蚀命"] = new("蚀命", "legendary.poison.life_erosion", "蚀命", "毒伤最大生命附加"),
            ["毒爆"] = new("毒爆", "legendary.poison.venom_burst", "毒爆", "毒层变化攻击成长"),
            ["余烬之核"] = new("余烬之核", "legendary.fire.ember_core", "余烬之核", "高伤害余烬生成与消耗治疗"),
            ["灰烬循环"] = new("灰烬循环", "legendary.fire.ash_cycle", "灰烬循环", "洗牌余烬与消耗转抽牌资源"),
            ["血潮"] = new("血潮", "legendary.water.blood_tide", "血潮", "主弹生命支付与潮汐专精吸血")
        };

    public static IReadOnlyCollection<LegendaryAbilityStatusDefinition> All => Definitions.Values.ToArray();

    public static LegendaryAbilityStatusDefinition Get(string cardId) =>
        Definitions.TryGetValue(cardId, out var definition)
            ? definition
            : throw new KeyNotFoundException($"Unknown legendary ability status '{cardId}'.");

    public static bool Contains(string cardId) => Definitions.ContainsKey(cardId);
}
