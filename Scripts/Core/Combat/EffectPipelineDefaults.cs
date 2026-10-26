using Magicians.Core.Cards;

namespace Magicians.Core.Combat;

public static class EffectPipelineDefaults
{
    public static EffectPipeline Create(CardDatabase database, CardEffectRegistry registry)
    {
        var resolvers = registry.ImplementedCardIds.Select(id =>
            id is "岩核爆破" or "万钧碎盾" ? (ICardEffectResolver)new ActiveShieldBurstResolver(id)
            : CombatCardExecution.Immediate.Contains(id) ? new BasicImmediateEffectResolver(id)
            : new BaseStatsOrDeckEffectResolver(id));
        return new EffectPipeline(resolvers);
    }
}
