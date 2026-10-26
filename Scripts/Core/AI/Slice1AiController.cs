using Magicians.Core.Common;
using Magicians.Core.Match;

namespace Magicians.Core.AI;

public sealed class Slice1AiController
{
    private readonly IDraftPolicy _draftPolicy;

    public Slice1AiController(IDraftPolicy? draftPolicy = null) =>
        _draftPolicy = draftPolicy ?? new Slice1DraftPolicy();

    public void CompleteDraft(MatchCoordinator coordinator, PlayerId player)
    {
        while (coordinator.CurrentState.Phase == MatchPhase.Draft)
        {
            var state = coordinator.CurrentState;
            var playerState = state.Players[player];
            if (playerState.Draft.IsCompleted)
                return;
            var decision = _draftPolicy.Choose(new DraftObservation(playerState));
            var sequence = new CommandSequence(state.EventSequence + 1);
            var result = decision.Kind switch
            {
                DraftDecisionKind.Buy => coordinator.Submit(new BuyCardCommand(
                    state.Id, player, decision.OfferSlotId!, sequence)),
                DraftDecisionKind.Skip => coordinator.Submit(new SkipOfferCommand(
                    state.Id, player, decision.OfferSlotId!, sequence)),
                _ => coordinator.Submit(new FinishDraftCommand(state.Id, player, sequence))
            };
            if (!result.Accepted)
            {
                if (decision.Kind == DraftDecisionKind.Buy && result.Rejection?.Code is "DuplicateCard" or "SpecializedElementRestriction" or "LegendaryLimitReached" or "RouteAlreadyOwned")
                {
                    var skip = coordinator.Submit(new SkipOfferCommand(state.Id, player, decision.OfferSlotId!, sequence));
                    if (skip.Accepted) continue;
                }
                throw new InvalidOperationException($"AI draft command rejected: {result.Rejection?.Code}");
            }
        }
    }
}
