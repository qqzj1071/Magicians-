using Godot;
using Magicians.Core.Cards;
using Magicians.Core.Combat;
using Magicians.Core.Common;

namespace Magicians.Presentation;

public partial class CombatStatusPanel : Window
{
    private VBoxContainer _body = null!;
    private PlayerId _player;
    public void Open(BattleInstance battle, PlayerId player, CardDatabase cards)
    {
        _player = player;
        var state = battle.State;
        var self = state.A.Player == player ? state.A : state.B;
        _body ??= new VBoxContainer();
        if (_body.GetParent() is null) { AddChild(_body); _body.SetAnchorsAndOffsetsPreset(Control.LayoutPreset.FullRect); }
        foreach (var child in _body.GetChildren()) { _body.RemoveChild(child); child.QueueFree(); }
        Title = $"{player.Value} · 当前状态";
        Size = new Vector2I(620, 720);
        AddLine($"攻击 {self.Attack} · 防御 {self.Defense} · 生命 {self.Life} · 护盾 {self.Shield} · 费用 {self.Energy}");
        AddLine($"行动值 {state.ActionValue} · 下次发射 {self.NextFire} · 发射间隔修正 {self.AttackIntervalModifier}");
        AddLine($"飞弹附魔：火 {self.FireLayers} · 水 {self.WaterLayers} · 土 {self.EarthLayers} · 风 {self.WindLayers} · 毒附魔 {self.PoisonEnchantmentLayers} · 目标毒层 {self.PoisonLayers}");
        AddLine($"余烬 {self.Embers}（{(self.EmberDamageActive ? "已激活" : "未激活")}） · 潮汐值 {self.Tides:0.##}（{(self.TideActive ? "已激活" : "未激活")}）");
        AddLine($"下一发增伤 {self.NextMissileBonusPercent}% +{self.NextMissileBonusFlat} · 下一发易伤/受伤倍率 {self.NextIncomingDamageMultiplierPercent}% +{self.NextIncomingDamageFlat}");
        AddLine($"主弹护盾穿透 {self.NextShieldPenetrationPercent}% · 主弹防御穿透 {self.NextDefensePenetrationPercent + self.MainDefensePenetrationPercent}% · 下一发间隔 {self.NextGapAdjustment}");
        AddLine($"疾风 {self.WindGaleActive} · 风痕 {self.WindTraceLayers} · 壁垒 {self.EarthBarrierActive} · 瘟疫 {self.PlagueActive}");
        AddLine($"回复减益 {self.HealingReductionPercent}% · 受伤倍率 {self.BattleIncomingDamageMultiplierPercent}% · 破盾反应 {self.ShieldBreakReturnFlat} +{self.ShieldBreakReturnPercent}%");
        AddLine("永久攻防加减值不在此处重复显示；战斗面板会实时显示最终攻防。");
        var close = new Button { Text = "关闭状态" };
        close.Pressed += QueueFree;
        _body.AddChild(close);
        CloseRequested += QueueFree;
        PopupCentered();
    }
    private void AddLine(string text) => _body.AddChild(new Label { Text = text, AutowrapMode = TextServer.AutowrapMode.WordSmart });
}

