namespace Magicians.Core.Cards;

public enum CardEffectSupport
{
    Implemented,
    Unsupported
}

public sealed record CardEffectRegistration(string CardId, CardEffectSupport Support, string Reason);

/// <summary>Single allow-list for effects that the current combat executor can actually resolve.</summary>
public sealed class CardEffectRegistry
{


    private readonly IReadOnlyDictionary<string, CardEffectRegistration> _registrations;

    private CardEffectRegistry(IReadOnlyDictionary<string, CardEffectRegistration> registrations) => _registrations = registrations;

    public IReadOnlyCollection<CardEffectRegistration> All => _registrations.Values.ToArray();
    public IReadOnlySet<string> ImplementedCardIds =>
        _registrations.Values.Where(item => item.Support == CardEffectSupport.Implemented)
            .Select(item => item.CardId).ToHashSet(StringComparer.Ordinal);
    public IReadOnlyList<CardEffectRegistration> UnsupportedCards =>
        _registrations.Values.Where(item => item.Support == CardEffectSupport.Unsupported)
            .OrderBy(item => item.CardId, StringComparer.Ordinal).ToArray();

    public bool IsImplemented(string cardId) =>
        _registrations.TryGetValue(cardId, out var registration) && registration.Support == CardEffectSupport.Implemented;

    public CardEffectRegistration Get(string cardId) =>
        _registrations.TryGetValue(cardId, out var registration)
            ? registration
            : throw new KeyNotFoundException($"No effect registration exists for '{cardId}'.");

    public static CardEffectRegistry CreateSlice1(CardDatabase database)
    {
        var registrations = database.All.ToDictionary(
            definition => definition.Name,
            definition => Magicians.Core.Combat.CombatCardExecution.IsSupported(definition.Name)
                ? new CardEffectRegistration(definition.Name, CardEffectSupport.Implemented, "Slice1CombatEngine")
                : new CardEffectRegistration(definition.Name, CardEffectSupport.Unsupported, "EffectResolverNotImplemented"),
            StringComparer.Ordinal);
        return new CardEffectRegistry(registrations);
    }

    public void RequireImplemented(string cardId)
    {
        if (!IsImplemented(cardId))
        {
            var registration = Get(cardId);
            throw new NotSupportedException($"UnsupportedCardEffect: {cardId}; reason={registration.Reason}");
        }
    }
}

public static class FullPoolActivationGuard
{
    public static void RequireAllEffectsImplemented(Slice1CardPool pool, CardEffectRegistry registry)
    {
        var unsupported = pool.OfferPool.Select(entry => entry.CardId)
            .Where(cardId => !registry.IsImplemented(cardId))
            .Distinct(StringComparer.Ordinal)
            .OrderBy(cardId => cardId, StringComparer.Ordinal)
            .ToArray();
        if (unsupported.Length > 0)
            throw new InvalidOperationException(
                $"FullPoolActivationBlocked: {unsupported.Length} card effects are unsupported. First={string.Join(',', unsupported.Take(8))}");
    }
}






















