using Magicians.Application;
using Magicians.Core.Combat;
using Magicians.Core.Common;
using Magicians.Presentation;

namespace Magicians.Tests;

public static class CombatFeedbackRegression
{
    public static void Run(string root)
    {
        using var session = GameSession.CreateSlice1(root);
        var human = new PlayerId("human");
        var enemy = new PlayerId("ai-1");
        if (session.Cards.Count != 252 || session.Cards.TryGet("守势", out _) ||
            session.FullCardPool.OfferPool.Any(c => c.CardId == "守势") ||
            session.FullCardPool.OfferPool.Sum(c => c.Count) != 1052 ||
            session.CardProfiles.All.Any(c => c.CardId == "守势"))
            throw new InvalidDataException("Retired duplicate still exists in current playable resources.");
        var events = new List<CombatEvent>
        {
            new(1, 0, "CardPlayed", human, "攻击强化"),
            new(1, 0, "CardPlayed", enemy, "防御强化")
        };
        events.AddRange(Enumerable.Range(0, 20).Select(i => new CombatEvent(1, 0, "MainMissile", enemy, LifeDamage: 1)));
        var text = CombatLogText.Exchanges(events, human);
        if (!text.Contains("你：【攻击强化】", StringComparison.Ordinal) || !text.Contains("对手AI：【防御强化】", StringComparison.Ordinal))
            throw new InvalidDataException("Damage events hid the paired card-play log.");
        events.Add(new(2, 0, "CardPlayed", enemy, "短促"));
        if (!CombatLogText.Exchanges(events, human).Contains("你：本步未出牌；对手AI：【短促】", StringComparison.Ordinal))
            throw new InvalidDataException("Opponent-only play after ending the window was hidden.");
        var missiles = CombatLogText.Missiles(new[]
        {
            new CombatEvent(1, 100, "MainMissile", human, Amount: 99, ShieldDamage: 20, LifeDamage: 40),
            new CombatEvent(1, 100, "Submissile", enemy, ShieldDamage: 15, LifeDamage: 0),
            new CombatEvent(1, 100, "WindGaleTrueShot", enemy, LifeDamage: 12),
            new CombatEvent(1, 100, "EmberSpent", human, Amount: 3),
            new CombatEvent(1, 100, "ConditionalMissileHealing", human, Amount: 8),
            new CombatEvent(1, 100, "CardDrawn", enemy, "时光倒流"),
            new CombatEvent(1, 100, "Fatigue", human, Amount: 50)
        }, human);
        if (!missiles.Contains("你 → 对手 · 主弹结算：护盾损失20，生命损失40", StringComparison.Ordinal) ||
            !missiles.Contains("对手 → 你 · 副弹结算：护盾损失15，生命损失0", StringComparison.Ordinal) ||
            !missiles.Contains("疾风真伤副弹结算：护盾损失0，生命损失12", StringComparison.Ordinal) ||
            !missiles.Contains("消耗余烬3层", StringComparison.Ordinal) || !missiles.Contains("回复生命8点", StringComparison.Ordinal) ||
            missiles.Contains("时光倒流", StringComparison.Ordinal) || missiles.Contains("99", StringComparison.Ordinal) || missiles.Contains("50", StringComparison.Ordinal))
            throw new InvalidDataException("Missile log has incorrect attribution, actual damage or hidden/unrelated events.");

        session.BeginDraft();
        foreach (var player in session.Coordinator.CurrentState.Players.Values.ToArray())
        {
            var state = session.Coordinator.CurrentState;
            session.Coordinator.Submit(new FinishDraftCommand(state.Id, player.Id, new(state.EventSequence + 1)));
        }
        var manager = session.EnsureBattleInstances();
        var battleId = session.HumanBattle!.Pairing.BattleId;
        for (var i = 0; i < 500 && manager.Instances[battleId].State.Phase != CombatPhase.Finished; i++)
            foreach (var actor in new[] { human, enemy })
            {
                var combat = manager.Instances[battleId].State;
                if (combat.Phase == CombatPhase.Finished || combat.EndedWindows.Contains(actor) || combat.PendingActions.Any(p => p.Player == actor)) continue;
                var command = new CombatCommand(battleId, actor, combat.Revision, new CombatAction(CombatActionKind.EndWindow));
                if (!session.SubmitCombat(command).Accepted) throw new InvalidDataException("Feedback test battle command rejected.");
            }
        var applied = session.ApplyFinishedBattle(battleId);
        if (!applied.Accepted || session.BattleAnnouncements.Count != 1)
            throw new InvalidDataException("Completed battle was not broadcast immediately.");
        var announcement = session.BattleAnnouncements.Single().Text;
        foreach (var change in applied.Events.OfType<TournamentLifeChangedEvent>())
            if (!announcement.Contains($"扣除{change.Damage}点赛事生命", StringComparison.Ordinal) ||
                !announcement.Contains($"{change.PreviousLife} → {change.NewLife}", StringComparison.Ordinal))
                throw new InvalidDataException("Broadcast did not use actual settled tournament damage.");
        if (session.ApplyFinishedBattle(battleId).Accepted || session.BattleAnnouncements.Count != 1)
            throw new InvalidDataException("Repeated battle result was broadcast twice.");
        var stateAfter = applied.State;
        var doubleResult = manager.GetResult(battleId) with { Winner = null, DoubleElimination = true };
        var doubleEvents = new GameEvent[]
        {
            new TournamentLifeChangedEvent(stateAfter.Id, 1, 1, "", human, 2, -2, 4),
            new TournamentLifeChangedEvent(stateAfter.Id, 1, 2, "", enemy, 8, 4, 4)
        };
        var doubleText = BattleResultAnnouncement.Create(doubleResult, stateAfter, doubleEvents).Text;
        if (!doubleText.Contains("同时倒下", StringComparison.Ordinal) || !doubleText.Contains("2 → -2", StringComparison.Ordinal) ||
            !doubleText.Contains("8 → 4", StringComparison.Ordinal))
            throw new InvalidDataException("Double-knockout broadcast hid a deduction or signed life.");
        var noLoss = BattleResultAnnouncement.Create(doubleResult with { Winner = human, DoubleElimination = false }, stateAfter, Array.Empty<GameEvent>()).Text;
        if (!noLoss.Contains("战胜了", StringComparison.Ordinal) || !noLoss.Contains("不扣赛事生命", StringComparison.Ordinal))
            throw new InvalidDataException("Ghost broadcast invented tournament damage.");
        Godot.GD.Print("COMBAT_FEEDBACK_OK retirement=252/1052 paired-log=OK settlement-broadcast=OK double-knockout=OK duplicate-result=OK");
    }
}
