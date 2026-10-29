using Godot;
using Magicians.Application;
using Magicians.Core.Combat;
using Magicians.Core.Common;
namespace Magicians.Presentation;

// Viewing the revealed candidates commits the player to completing this search.
// Closing the title bar or pressing Escape cannot return to the battle board.
public partial class SearchSelectionPanel : Window
{
    public IReadOnlyList<CardInstanceId> Selected => _selected;
    private readonly List<CardInstanceId> _selected = new();
    public void Open(GameSession session, SearchSelectionSession search, Action<CardInstanceId[]> commit)
    {
        Title = $"{search.CardId} · 选择置顶卡牌";
        Transient = true; Exclusive = true; Unresizable = true;
        CloseRequested += () => { }; // Deliberately no cancel route after reveal.
        var size = GetParent<Control>().GetWindow().Size;
        var width = Math.Max(320, Math.Min(1360, (int)size.X - 48));
        var height = Math.Max(280, Math.Min(860, (int)size.Y - 48));
        var column = new VBoxContainer { Name = "Layout", OffsetLeft=16, OffsetTop=16, OffsetRight=-16, OffsetBottom=-16 };
        AddChild(column); column.SetAnchorsAndOffsetsPreset(Control.LayoutPreset.FullRect);
        column.OffsetLeft=16;column.OffsetTop=16;column.OffsetRight=-16;column.OffsetBottom=-16;
        column.AddChild(new Label { Text = $"检索已开始，不能取消。请选择{(search.MaximumSelections == 1 ? "1" : "至多" + search.MaximumSelections)}张后确认。", AutowrapMode=TextServer.AutowrapMode.WordSmart });
        var order = new Label { Name="Order", Text="第一张选择的牌将位于牌堆最上方。", AutowrapMode=TextServer.AutowrapMode.WordSmart };
        column.AddChild(order);
        var scroll = new ScrollContainer { Name="Scroll", SizeFlagsVertical=Control.SizeFlags.ExpandFill, HorizontalScrollMode=ScrollContainer.ScrollMode.Disabled };
        column.AddChild(scroll);
        var columns = Math.Clamp((width-48)/250,1,4);
        var grid = new GridContainer { Name="Cards", Columns=columns, SizeFlagsHorizontal=Control.SizeFlags.ExpandFill };
        grid.AddThemeConstantOverride("h_separation",12);grid.AddThemeConstantOverride("v_separation",12);scroll.AddChild(grid);
        var confirm = new Button { Name="Confirm", Text="确认置顶并打出检索牌", Disabled=search.MaximumSelections==1, CustomMinimumSize=new Vector2(0,44) };
        var buttons = new List<(CardInstanceId Id, CheckButton Button)>();
        var scene = GD.Load<PackedScene>("res://Scenes/UI/CardView.tscn");
        foreach (var candidate in search.Candidates)
        {
            var row = new VBoxContainer { SizeFlagsHorizontal=Control.SizeFlags.ExpandFill };
            var card = scene.Instantiate<CardView>();
            var cardWidth=Math.Clamp((width-64-(columns-1)*12)/columns,200,310);
            card.CustomMinimumSize=new Vector2(cardWidth,cardWidth*1.618f);
            row.AddChild(card);
            var battle=session.HumanBattle;
            var actor=battle?.State.A.Player.Value=="human" ? battle.State.A : battle?.State.B;
            card.Bind(session.CardProfiles.Get(candidate.CardId),combat:true,enchantmentApplied:actor?.FirstPlayed.Contains(candidate.InstanceId)==true);
            var button = new CheckButton { Text="选择置顶", Name="Select" };
            button.SetMeta("card_instance",candidate.InstanceId.Value);
            buttons.Add((candidate.InstanceId,button));
            button.Toggled += enabled => {
                if(enabled && _selected.Count>=search.MaximumSelections){button.SetPressedNoSignal(false);return;}
                if(enabled)_selected.Add(candidate.InstanceId);else _selected.Remove(candidate.InstanceId);
                foreach(var item in buttons) {
                    var position=_selected.IndexOf(item.Id);
                    item.Button.Text=position<0?"选择置顶":$"第{position+1}张置顶";
                    item.Button.Disabled=position<0 && _selected.Count>=search.MaximumSelections;
                }
                order.Text=_selected.Count==0?"未选择卡牌（确认后仍会打出并消耗检索牌）":
                    "置顶顺序："+string.Join(" → ",_selected.Select(id=>search.Candidates.Single(c=>c.InstanceId==id).CardId));
                confirm.Disabled=search.MaximumSelections==1 && _selected.Count!=1;
            };
            row.AddChild(button);grid.AddChild(row);
        }
        var committed=false;
        confirm.Pressed += () => {
            if(committed || confirm.Disabled)return;
            committed=true;confirm.Disabled=true;
            commit(_selected.ToArray());QueueFree();
        };
        column.AddChild(confirm);
        PopupCentered(new Vector2I(width,height));
    }
    public override void _UnhandledKeyInput(InputEvent input)
    {
        if(input is InputEventKey { Pressed:true, Keycode:Key.Escape }) GetViewport().SetInputAsHandled();
    }
}
