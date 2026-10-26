using Magicians.Application;
using Magicians.Core.AI;
using Magicians.Core.Cards;
using Magicians.Core.Combat;
using Magicians.Core.Common;
using Magicians.Core.Match;

namespace Magicians.Tests;

public static class FullTournamentRegression
{
    public static void Run(string root)
    {
        VerifySignedPlacements(root, new[] { 5, 4, 3, 2 }, 1);
        VerifySignedPlacements(root, new[] { 5, 5, 4, 4 }, 2);
        VerifySignedPlacements(root, new[] { 11, 10, 9, 8 }, 1);
        VerifyGhostRound(root);
        var replayHashes = new Dictionary<int, string>();
        foreach (var seed in new[] { 20261024, 20261026, 20261024, 20261026 })
        {
            using var session = GameSession.CreateSlice1(root, seed);
            session.BeginDraft();
            var human = new PlayerId("human");
            var commands = 0;
            var combatEvents = new List<(int Round, BattleId Battle, CombatEvent Event)>();
            while (session.Coordinator.CurrentState.Phase != MatchPhase.Finished)
            {
                var match = session.Coordinator.CurrentState;
                if (match.Phase != MatchPhase.Combat) DraftAllocationRegression.VerifyInventory(match, session.CardPool);
                if (++commands > 100000 || match.Round > 128)
                    throw new InvalidDataException("Full tournament did not converge within its regression budget.");
                if (match.Phase == MatchPhase.Draft)
                {
                    foreach (var player in match.Players.Values.Where(p => p.TournamentLife > 0).ToArray())
                        session.CompleteDraftFor(player.Id);
                }
                else if (match.Phase == MatchPhase.Combat)
                {
                    var manager = session.EnsureBattleInstances();
                    foreach (var id in manager.Instances.Keys.OrderBy(id => id.Value, StringComparer.Ordinal).ToArray())
                    {
                        foreach (var actor in new[] { manager.Instances[id].State.A.Player, manager.Instances[id].State.B.Player })
                        {
                            var instance = manager.Instances[id];
                            if (instance.State.Phase != CombatPhase.Decision || instance.State.EndedWindows.Contains(actor) ||
                                instance.State.PendingActions.Any(p => p.Player == actor)) continue;
                            var result = session.SubmitCombat(new CombatCommand(id, actor, instance.State.Revision,
                                session.ChooseAutomaticAction(instance, actor)));
                            if (!result.Accepted) throw new InvalidDataException("Trained replay combat rejected: " + result.Rejection?.Code);
                            combatEvents.AddRange(result.Events.Select(e => (match.Round, id, e)));
                        }
                        if (manager.Instances[id].State.Phase == CombatPhase.Finished &&
                            !session.Coordinator.CurrentState.BattleResults.Any(r => r.Battle == id))
                            session.ApplyFinishedBattle(id);
                    }
                }
                else if (match.Phase == MatchPhase.Settlement) session.AdvanceRound();
                else throw new InvalidDataException("Unexpected tournament phase: " + match.Phase);
            }
            var final = session.Coordinator.CurrentState;
            if (session.RecordedBattles.Count != final.RoundHistory.Sum(r => r.Pairings.Count) ||
                session.RecordedBattles.Any(b => b.Result is null) ||
                session.RecordedBattles.Sum(b => b.Plays.Count) != combatEvents.Count(e => e.Event.Kind == "CardPlayed"))
                throw new InvalidDataException("Post-match history lost a round, result or committed card play.");
            var standings = TournamentStandings.Calculate(final);
            if (standings.Count != 4 || TournamentStandings.Champions(final).Count == 0 || final.RoundHistory.Count != final.Round)
                throw new InvalidDataException("Full tournament did not produce complete standings and round history.");
            var hash = StateHasher.Hash(final);
            if (replayHashes.TryGetValue(seed, out var previous) && previous != hash)
                throw new InvalidDataException("Full tournament replay diverged for seed " + seed);
            var runNumber = replayHashes.ContainsKey(seed) ? 2 : 1;
            ReplayArtifacts.Save(root, seed, runNumber, session, combatEvents);
            replayHashes[seed] = hash;
            Godot.GD.Print($"FULL_TOURNAMENT_OK seed={seed} rounds={final.Round} commands={commands} champions={string.Join(',', TournamentStandings.Champions(final))}");
        }
        ReplayArtifacts.SaveIndex(root);
    }

    private static void VerifySignedPlacements(string root, int[] lives, int expectedChampions)
    {
        using var session = GameSession.CreateSlice1(root);
        session.BeginDraft();
        foreach (var player in session.Coordinator.CurrentState.Players.Values.ToArray())
            session.Coordinator.Submit(new FinishDraftCommand(session.Coordinator.CurrentState.Id, player.Id,
                new(session.Coordinator.CurrentState.EventSequence + 1)));
        var state = session.Coordinator.CurrentState;
        var ordered = state.Players.Keys.OrderBy(p => p.Value, StringComparer.Ordinal).ToArray();
        var players = state.Players.ToDictionary(p => p.Key, p => p.Value with { TournamentLife = lives[Array.IndexOf(ordered, p.Key)] });
        var coordinator = MatchCoordinator.Restore(session.Cards, session.CardPool, state with { Round = 17, Players = players });
        foreach (var pair in state.Pairings)
        {
            var applied = coordinator.ApplyBattleResult(new BattleResult(pair.BattleId, pair.PlayerA, pair.PlayerB, null, 0, true));
            if (!applied.Accepted) throw new InvalidDataException("Signed placement settlement rejected.");
        }
        var advance = coordinator.Submit(new AdvanceSettlementCommand(state.Id, new PlayerId("human"), new(coordinator.CurrentState.EventSequence + 1)));
        if (!advance.Accepted || TournamentStandings.Champions(advance.State).Count != expectedChampions ||
            advance.State.Players.Values.Any(p => p.TournamentLife > 0 || p.EliminatedRound != 17))
            throw new InvalidDataException("Signed-life champion and shared-champion rules failed.");
        var championEvent = advance.State.EventLog.OfType<TournamentFinishedEvent>().Last();
        if (championEvent.Champions.Count != expectedChampions)
            throw new InvalidDataException("Tournament finish event disagrees with standings.");
        var placements = TournamentStandings.Calculate(advance.State);
        if (placements[0].RemainingLife < placements[^1].RemainingLife || placements[0].Place != 1)
            throw new InvalidDataException("Same-round elimination standings must use signed remaining life.");
    }

    private static void VerifyGhostRound(string root)
    {
        using var session = GameSession.CreateSlice1(root);
        session.BeginDraft();
        foreach (var player in session.Coordinator.CurrentState.Players.Values.ToArray())
            session.Coordinator.Submit(new FinishDraftCommand(session.Coordinator.CurrentState.Id, player.Id,
                new(session.Coordinator.CurrentState.EventSequence + 1)));
        var state = session.Coordinator.CurrentState;
        var victim = state.Pairings[0].PlayerA;
        var players = state.Players.ToDictionary(p => p.Key, p => p.Value with { TournamentLife = p.Key == victim ? 1 : 100 });
        var coordinator = MatchCoordinator.Restore(session.Cards, session.CardPool, state with { Players = players });
        foreach (var pair in state.Pairings)
            coordinator.ApplyBattleResult(new BattleResult(pair.BattleId, pair.PlayerA, pair.PlayerB, pair.PlayerB, 1000, false));
        var result = coordinator.Submit(new AdvanceSettlementCommand(state.Id, new PlayerId("human"), new(coordinator.CurrentState.EventSequence + 1)));
        if (!result.Accepted || result.State.GhostSnapshots.Count != 1 || result.State.Players[victim].Kind != PlayerKind.Ghost)
            throw new InvalidDataException("Three-survivor round must retain one eliminated deck snapshot.");
        coordinator.Submit(new BeginRoundDraftCommand(state.Id, new PlayerId("human"), new(coordinator.CurrentState.EventSequence + 1)));
        foreach (var player in coordinator.CurrentState.Players.Values.Where(p => p.TournamentLife > 0).ToArray())
            coordinator.Submit(new FinishDraftCommand(state.Id, player.Id, new(coordinator.CurrentState.EventSequence + 1)));
        var manager = BattleInstanceManager.Create(coordinator.CurrentState, new Slice1CombatEngine(session.Cards));
        var ghost = manager.Instances.Values.Single(i => i.Pairing.PlayerA == victim || i.Pairing.PlayerB == victim);
        if (ghost.State.Phase != CombatPhase.Decision)
            throw new InvalidDataException("Ghost matches must actually fight rather than grant automatic victory.");
        for (var step = 0; step < 400 && manager.Instances[ghost.Pairing.BattleId].State.Phase != CombatPhase.Finished; step++)
        {
            var current = manager.Instances[ghost.Pairing.BattleId].State;
            foreach (var player in new[] { current.A.Player, current.B.Player })
            {
                current = manager.Instances[ghost.Pairing.BattleId].State;
                if (current.Phase == CombatPhase.Finished || current.EndedWindows.Contains(player) || current.PendingActions.Any(p => p.Player == player)) continue;
                manager.Submit(new CombatCommand(current.Battle, player, current.Revision, new CombatAction(CombatActionKind.EndWindow)));
            }
        }
        if (manager.Instances[ghost.Pairing.BattleId].State.Phase != CombatPhase.Finished)
            throw new InvalidDataException("Ghost battle did not finish.");
        var beforeLife = coordinator.CurrentState.Players[victim].TournamentLife;
        coordinator.ApplyBattleResult(manager.GetResult(ghost.Pairing.BattleId));
        if (coordinator.CurrentState.Players[victim].TournamentLife != beforeLife)
            throw new InvalidDataException("Ghost tournament life must remain frozen.");
        Godot.GD.Print("GHOST_ROUND_OK");
    }
}

