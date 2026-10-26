namespace Magicians.Core.Combat;

/// <summary>Records actual ember consumption for future ledger redemptions.</summary>
public static class EmberConsumption
{
    public static CombatResourceState Record(CombatResourceState state, int actualSpent) => state with
    {
        UnredeemedEmbersSpent = checked(state.UnredeemedEmbersSpent + Math.Max(0, actualSpent))
    };

    public static CombatantState Record(CombatantState state, int actualSpent) => state with
    {
        UnredeemedEmbersSpent = checked(state.UnredeemedEmbersSpent + Math.Max(0, actualSpent))
    };
}
