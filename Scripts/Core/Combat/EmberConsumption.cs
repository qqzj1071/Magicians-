namespace Magicians.Core.Combat;

/// <summary>Records actual ember consumption for future ledger redemptions.</summary>
public static class EmberConsumption
{
    public static CombatResourceState Record(CombatResourceState state, int actualSpent) => state with
    {
        UnredeemedEmbersSpent = checked(state.UnredeemedEmbersSpent + Math.Max(0, actualSpent)),
        AshCyclePendingCredit = state.AshCycleActive && state.EmberDamageActive
            ? Math.Min(3, state.AshCyclePendingCredit + Math.Max(0, actualSpent)) : state.AshCyclePendingCredit
    };

    public static CombatantState Record(CombatantState state, int actualSpent) => state with
    {
        UnredeemedEmbersSpent = checked(state.UnredeemedEmbersSpent + Math.Max(0, actualSpent)),
        AshCyclePendingCredit = state.AshCycleActive && state.EmberDamageActive
            ? Math.Min(3, state.AshCyclePendingCredit + Math.Max(0, actualSpent)) : state.AshCyclePendingCredit
    };
}
