namespace Magicians.Core.Combat;

/// <summary>Active shield consumption is not an enemy shield-break event.</summary>
public sealed class ActiveShieldBurstResolver : ICardEffectResolver
{
    public ActiveShieldBurstResolver(string cardId) => CardId = cardId;
    public string CardId { get; }

    public IReadOnlyList<EffectMutation> Resolve(EffectContext context, EffectTiming timing)
    {
        if (timing != EffectTiming.OnPlay) return Array.Empty<EffectMutation>();
        var source = context.SourceResources;
        var target = context.TargetResources;
        var heavy = CardId == "万钧碎盾";
        source = source with { ShieldDecay = source.ShieldDecay.OnOrdinaryGain(source.Shield), Shield = CombatMath.AddOrdinaryShield(source.Shield, heavy ? 100 : 80) };
        if (!source.EarthBarrierActive)
            return new[] { new EffectMutation(CardId, timing, 0, source, target, Array.Empty<CombatEvent>()) };

        var consumed = source.Shield;
        source = source with { Shield = 0, TemporaryShield = 0 };
        var upgraded = source.EarthSpecialized && source.ShieldBreakReturnPercent > 0;
        var raw = Math.Max(0m, consumed * source.EarthLayers * (upgraded ? 0.045m : 0.03m)
            - target.Defense * 0.50m);
        // Shield-burst damage uses its own defense formula, then source fire layers.
        // Ordinary projectile bonuses, wind penetration and embers do not apply.
        var damage = CombatMath.Ceiling(raw * (1 + source.FireLayers * (source.FireSpecialized ? 0.02m : 0.01m)));
        var split = CombatMath.SplitShieldBurst(damage, target.Shield,
            0);
        var absorbed = split.Shield;
        var lifeDamage = split.Life;
        target = target with
        {
            Shield = target.Shield - absorbed,
            TemporaryShield = Math.Max(0, target.TemporaryShield - absorbed),
            Life = target.Life - lifeDamage
        };
        if (absorbed > 0 && target.Shield == 0)
            target = target with
            {
                ShieldBrokenThisBattle = true,
                Defense = target.Defense + (target.ShieldBreakDefenseMarkerActive ? 6 : 0),
                NextDrawBonus = target.NextDrawBonus + (target.ShieldBreakDrawMarkerActive ? 1 : 0),
                ShieldBreakDefenseMarkerActive = false,
                ShieldBreakDrawMarkerActive = false
            };
        if (target.Life > 0)
            source = source with { Shield = heavy ? CombatMath.Ceiling(consumed * 0.30m) : 30 };

        return new[] { new EffectMutation(CardId, timing, 0, source, target,
            new[] { new CombatEvent(0, context.ActionValue, "ActiveShieldBurst", context.Source,
                CardId, damage, absorbed, lifeDamage) }) };
    }
}

