using Godot;
using Magicians.Application;
using Magicians.Core.Common;
using Magicians.Core.Combat;

namespace Magicians.Presentation;

public partial class BattleReviewPanel : VBoxContainer
{
    private OptionButton _rounds = null!;
    private OptionButton _battles = null!;
    private Tree _plays = null!;
    private Label _result = null!;
    private HBoxContainer _cards = null!;
    private RecordedBattle[] _available = Array.Empty<RecordedBattle>();
    private RecordedBattle[] _roundBattles = Array.Empty<RecordedBattle>();
    private RecordedBattle? _selected;
    private int _selectedRound;
    private readonly Dictionary<long, CombatEvent[]> _steps = new();

    public override void _Ready()
    {
        AddChild(new Label { Text = "逐轮出牌复盘 · 选择轮次与对局，点击记录查看双方完整卡面" });
        var filters = new HBoxContainer(); AddChild(filters);
        _rounds = new OptionButton(); filters.AddChild(_rounds);
        _battles = new OptionButton(); filters.AddChild(_battles);
        _result = new Label { AutowrapMode = TextServer.AutowrapMode.WordSmart }; AddChild(_result);
        _plays = new Tree { Columns = 4, HideRoot = true, ColumnTitlesVisible = true,
            SizeFlagsVertical = SizeFlags.ExpandFill, CustomMinimumSize = new Vector2(0, 160) };
        _plays.SetColumnTitle(0, "行动值"); _plays.SetColumnTitle(1, "同步步骤");
        _plays.SetColumnTitle(2, "我方 / A方出牌"); _plays.SetColumnTitle(3, "对手 / B方出牌");
        _plays.SetColumnExpand(0, false); _plays.SetColumnCustomMinimumWidth(0, 100);
        _plays.SetColumnExpand(1, false); _plays.SetColumnCustomMinimumWidth(1, 120);
        AddChild(_plays);
        var scroll = new ScrollContainer { CustomMinimumSize = new Vector2(0, 430), HorizontalScrollMode = ScrollContainer.ScrollMode.Auto };
        AddChild(scroll);
        _cards = new HBoxContainer(); scroll.AddChild(_cards);
        _rounds.ItemSelected += index => { _selectedRound = _rounds.GetItemId((int)index); RefreshBattles(); };
        _battles.ItemSelected += index => { _selected = _roundBattles[(int)index]; ShowBattle(); };
        _plays.ItemSelected += ShowCards;
    }

    public void Refresh()
    {
        if (_rounds is null || GameSession.Current is not { } session) return;
        _available = session.RecordedBattles.Where(b => b.Result is not null).ToArray();
        var rounds = _available.Select(b => b.Round).Distinct().OrderBy(r => r).ToArray();
        if (rounds.Length == 0) { _result.Text = "暂无已完成对局。"; return; }
        if (!rounds.Contains(_selectedRound)) _selectedRound = rounds[^1];
        _rounds.Clear();
        foreach (var round in rounds) _rounds.AddItem($"第{round}轮", round);
        _rounds.Select(Array.IndexOf(rounds, _selectedRound));
        RefreshBattles();
    }

    private void RefreshBattles()
    {
        var state = GameSession.Current!.Coordinator.CurrentState;
        _roundBattles = _available.Where(b => b.Round == _selectedRound).ToArray();
        _battles.Clear();
        foreach (var battle in _roundBattles)
            _battles.AddItem($"{state.Players[battle.Pairing.PlayerA].PublicInfo.DisplayName} vs {state.Players[battle.Pairing.PlayerB].PublicInfo.DisplayName}");
        var index = Array.IndexOf(_roundBattles, _selected);
        if (index < 0) index = Array.FindIndex(_roundBattles, b => b.Pairing.PlayerA.Value == "human" || b.Pairing.PlayerB.Value == "human");
        if (index < 0) index = 0;
        if (_roundBattles.Length == 0) return;
        _battles.Select(index); _selected = _roundBattles[index]; ShowBattle();
    }

    private void ShowBattle()
    {
        _plays.Clear(); _steps.Clear(); ClearCards();
        if (_selected is null) return;
        var session = GameSession.Current!;
        _result.Text = session.BattleAnnouncements.FirstOrDefault(a => a.Round == _selected.Round && a.Battle == _selected.Pairing.BattleId)?.Text ?? "对局已结束";
        var root = _plays.CreateItem();
        var own = _selected.Pairing.PlayerB.Value == "human" ? _selected.Pairing.PlayerB : _selected.Pairing.PlayerA;
        var opponent = own == _selected.Pairing.PlayerA ? _selected.Pairing.PlayerB : _selected.Pairing.PlayerA;
        _plays.SetColumnTitle(2, session.Coordinator.CurrentState.Players[own].PublicInfo.DisplayName + "出牌");
        _plays.SetColumnTitle(3, session.Coordinator.CurrentState.Players[opponent].PublicInfo.DisplayName + "出牌");
        foreach (var group in _selected.Plays.GroupBy(p => p.Revision))
        {
            var values = group.ToArray(); _steps[group.Key] = values;
            var row = _plays.CreateItem(root);
            row.SetText(0, values[0].ActionValue.ToString()); row.SetText(1, group.Key.ToString());
            row.SetText(2, Names(values.Where(e => e.Player == own)));
            row.SetText(3, Names(values.Where(e => e.Player != own)));
            row.SetMetadata(0, group.Key);
        }
        if (_selected.Plays.Count == 0) _result.Text += "（双方本场均未出牌）";
        if (root.GetFirstChild() is { } first) { first.Select(0); ShowCards(); }
    }

    private static string Names(IEnumerable<CombatEvent> plays)
    {
        var names = plays.Select(p => p.CardId).ToArray();
        return names.Length == 0 ? "本步未出牌" : string.Join("、", names);
    }

    private void ClearCards()
    {
        foreach (var child in _cards.GetChildren()) { _cards.RemoveChild(child); child.QueueFree(); }
    }

    private void ShowCards()
    {
        ClearCards();
        var item = _plays.GetSelected();
        if (item is null || !_steps.TryGetValue(item.GetMetadata(0).AsInt64(), out var events)) return;
        var session = GameSession.Current!;
        var scene = GD.Load<PackedScene>("res://Scenes/UI/CardView.tscn");
        foreach (var play in events)
        {
            var column = new VBoxContainer(); _cards.AddChild(column);
            column.AddChild(new Label { Text = session.Coordinator.CurrentState.Players[play.Player].PublicInfo.DisplayName + "打出" });
            var card = scene.Instantiate<CardView>(); column.AddChild(card);
            card.Bind(session.CardProfiles.Get(play.CardId!), combat: true);
        }
    }
}
