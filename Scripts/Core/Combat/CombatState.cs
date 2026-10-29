using Magicians.Core.Cards;
using Magicians.Core.Common;

namespace Magicians.Core.Combat;

public enum CombatPhase { Decision, Finished }
public enum CombatActionKind { PlayCard, EndWindow }

// SearchTarget is selected only from GetSearchCandidates for this decision snapshot.
public sealed record CombatAction(CombatActionKind Kind, CardInstanceId? Card = null,
    CardInstanceId? SearchTarget = null,
        IReadOnlyList<CardInstanceId>? SearchTargets = null);
public sealed record SearchSelectionSession(
    PlayerId Player,
    CardInstanceId SourceCard,
    string CardId,
    IReadOnlyList<CardInstance> Candidates,
    int MaximumSelections,
    bool PreserveSelectionOrder);
public sealed record CombatCommand(BattleId Battle, PlayerId Player, long ExpectedRevision,
    CombatAction Action);
public sealed record CombatantSetup(PlayerId Player, IReadOnlyList<CardInstance> Cards, int Seed);
public sealed record CombatSetup(BattleId Battle, CombatantSetup A, CombatantSetup B);
public sealed record CombatRewindSnapshot(
    int Life, int Attack, int Defense, int Shield,
    int WindLayers, int WaterLayers, int EarthLayers, int FireLayers,
    int Embers, bool EmberDamageActive,
    bool EarthBarrierActive, int ShieldBreakReturnPercent, int ShieldBreakReturnFlat,
    decimal AttackIntervalModifier, int PermanentIntervalMultiplierPercent,
    bool WindTraceActive, bool WindGaleActive, bool WindArrowActive,
    bool WindChaseActive, bool TideActive, int TideRefundPercent,
    int ActionValue, int ExpiresAtActionValue)
{
    public bool ShieldDecayActive { get; init; }
    public bool ManaContractActive { get; init; }
    public bool BastionHeartActive { get; init; }
    public bool BurningBloodlineActive { get; init; }
    public bool LifeSpringActive { get; init; }
}

public sealed record CombatantState(
    PlayerId Player,
    int Life,
    int Attack,
    int Defense,
    int Shield,
    int Energy,
    int DeckElementCount,
    string PrimaryElement,
    bool ElementForgeActive,
    int ElementForgeBonusLayers,
    int ElementForgePotentialLayers,
    int NextFire,
    decimal AttackIntervalModifier,
    int PermanentIntervalMultiplierPercent,
    int TemporaryIntervalMultiplierPercent,
    int NextIncomingDamageMultiplierPercent,
    int NextIncomingDamageFlat,
    int TemporaryShield,
    decimal Tides,
    bool TideActive,
    int NextTideDamageMultiplierPercent,
    int TideRefundPercent,
    bool BloodTideActive,
    int NextWaterShieldHealingMultiplierPercent,
    decimal ActualHealingThisBattle,
    int CardsPlayedThisWindow,
    bool GuardianBarrierActive,
    bool WarGodEmblemActive,
    CombatRewindSnapshot? RewindSnapshot,
    int NextPoisonOnHitLayers,
    int NextPoisonOnHitCharges,
    int ExtraPoisonTickCharges,
    bool PlagueLifeDamageActive,
    bool PoisonExplosionActive,
    bool PlagueActive,
    int PlagueAttackReduction,
    int PlagueDefenseReduction,
    int HealingReductionPercent,
    int HealingReductionUntilActionValue,
    int BattleIncomingDamageMultiplierPercent,
    int BattleIncomingDamageUntilActionValue,
    int NextDrawBonus,
    int NextEnergyBonus,
    decimal NextGapAdjustment,
    int WindLayers,
    int WaterLayers,
    int EarthLayers,
    bool EarthBarrierActive,
    int ShieldBreakReturnPercent,
    int ShieldBreakReturnFlat,
    bool ShieldBreakDefenseMarkerActive,
    bool ShieldBreakDrawMarkerActive,
    bool ShieldBrokenThisBattle,
    int FireLayers,
    int Embers,
    bool EmberDamageActive,
    bool EmberCoreActive,
    bool AshRebirthUsed,
    bool AshCycleActive,
    int ShuffleCount,
    int TemperBonusUses,
    int PoisonLayers,
    int PoisonEnchantmentLayers,
    int NextPoisonDecayActionValue,
    int PoisonDecayIntervalPercent,
    int PoisonDecayProtectionCharges,
    bool PoisonDecayKeepLast,
    bool PoisonSpecialized,
    bool FireSpecialized,
    bool WaterSpecialized,
    bool EarthSpecialized,
    bool WindSpecialized,
    int BattleAttackReduction,
    int BattleDefenseReduction,
    int NegativeSuppressedUntilActionValue,
    int TemporaryAttackReduction,
    int TemporaryDefenseReduction,
    int TemporaryPoisonLayers,
    IReadOnlyList<CardInstanceId> FirstPlayed,
    IReadOnlyList<CardInstance> DrawPile,
    IReadOnlyList<CardInstance> DiscardPile,
    IReadOnlyList<CardInstance> CurrentPool,
    IReadOnlyList<CardInstance> ExhaustedCards,
    int PendingSubmissiles,
    int PendingWindSubmissiles,
    int NextWindSubmissileFlat,
    int NextWindSubmissileAttackPercent,
    bool WindTraceActive,
    int WindTraceLayers,
    int WindTraceBonusLayers,
    bool WindGaleActive,
    int WindMainShotCount,
    int WindTraceExplosionMultiplierPercent,
    bool WindArrowActive,
    int NextShieldDamageMultiplierPercent,
    bool WindChaseActive,
    int LastMainMissileActionValue,
    int LastMainMissileActualDamage,
    int MainDamageBonusUntilDrawPercent,
    int NextMissileBonusPercent,
    int NextMissileBonusFlat,
    int NextMissileHealingPercent,
    int NextShieldPenetrationPercent,
    int MainShieldPenetrationUntilDrawPercent,
    int MainDefensePenetrationPercent,
    int NextDefensePenetrationPercent,
    int NextMainTemporaryShieldPercent,

    ulong RandomState)
{
    // Historical consumption is independent of temporary resources and rewinds.
    public int UnredeemedEmbersSpent { get; init; }
    public int AshCyclePendingCredit { get; init; }
    public IReadOnlyList<string> DrawnThisWindow { get; init; } = Array.Empty<string>();
    public ShieldDecayState ShieldDecay { get; init; } = new();
    public bool ManaContractActive { get; init; }
    public bool BastionHeartActive { get; init; }
    public bool BurningBloodlineActive { get; init; }
    public bool LifeSpringActive { get; init; }
    public int NextTideHealingRecordBonusPercent { get; init; }
}

public sealed record PendingAction(PlayerId Player, CombatAction Action);

// Pending submissions are private authority data; do not expose them to the other controller.
public sealed record CombatState(BattleId Battle, long Revision, int ActionValue,
    CombatPhase Phase, CombatantState A, CombatantState B,
    IReadOnlyList<PendingAction> PendingActions,
    IReadOnlyList<PlayerId> EndedWindows,
    PlayerId? Winner, bool DoubleKnockout);

// Combat events are separate from tournament events and never change tournament life.
public sealed record CombatEvent(long Revision, int ActionValue, string Kind, PlayerId Player,
    string? CardId = null, int Amount = 0, int ShieldDamage = 0, int LifeDamage = 0);
public sealed record CombatResolution(bool Accepted, CombatState State,
    IReadOnlyList<CombatEvent> Events, Rejection? Rejection);

public interface ICombatEngine
{
    CombatState Start(CombatSetup setup);
    CombatResolution Submit(CombatState state, CombatCommand command);
    IReadOnlyList<CardInstance> GetSearchCandidates(CombatState state, PlayerId player);
    SearchSelectionSession? GetSearchSession(CombatState state, PlayerId player, CardInstanceId sourceCard);
}


