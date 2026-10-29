"""Render saved balance results without rerunning any matches."""
from pathlib import Path
import argparse
import json

ROOT=Path(__file__).resolve().parents[2]
ELEMENTS={"fire":"火","water":"水","earth":"土","wind":"风","poison":"毒"}

def phase_means(report):
    result=[]
    for label,lo,hi in [("1—3轮",1,3),("4—6轮",4,6),("7—12轮",7,12)]:
        rows=[v for k,v in report["action_value_by_tournament_round"].items() if lo<=int(k)<=hi]
        result.append((label,sum(v["games"]*v["mean"] for v in rows)/sum(v["games"] for v in rows)))
    return result

def render(folder):
    d=json.loads((folder/"report.json").read_text(encoding="utf-8"))
    lines=["# v1.1 传奇路线平衡测试", "", f"本轮完成 {d['games']} 场四AI玩家完整赛事。排行榜按累计积分排序，第一至第四分别为 +3、+1、−1、−3。", "",
        "胜率定义为完整赛事的夺冠率；并列冠军平分1次夺冠。淘汰较晚者排名更高，同轮淘汰按结算后赛事血量（包括负数）降序；相同则平分占用名次积分。", "",
        "早于 ai-v1.1-route-pass3-round1-20261027 的旧报告存在淘汰顺序和末轮重复计人问题；本轮采用已修正统计，可与该批次起的有效报告比较。", "",
        f"随机种子命名空间：`{d['namespace']}`。同命名空间下的赛事编号可用于版本间对比；卡牌快照、AI模型与构筑规则的输入哈希保存在本目录。", "",
        f"统计校验：{d['validation']['players']} 条玩家结算，总积分 {d['validation']['total_points']:.0f}，总夺冠份额 {d['validation']['total_wins']:.0f}。", ""]
    missing_elements=d["validation"]["players"]-sum(r["selections"] for r in d["element_ranking"])
    missing_routes=d["validation"]["players"]-sum(r["selections"] for r in d["route_ranking"])
    lines.extend([f"未选择专精的玩家记录 {missing_elements} 条，未选择路线的玩家记录 {missing_routes} 条；不归入相应分组，因此分组积分之和可能不为0。", ""])
    for key,title in [("element_ranking","5种元素"),("route_ranking","15条路线")]:
        lines.extend([f"## {title}", "", "|排名|元素/路线|积分|选择次数|平均积分|夺冠率|", "|---:|---|---:|---:|---:|---:|"])
        for i,r in enumerate(d[key],1):
            lines.append(f"|{i}|{ELEMENTS.get(r['name'],r['name'])}|{r['score']:+.1f}|{r['selections']}|{r['mean_score']:+.3f}|{r['win_rate']:.1%}|")
        lines.append("")
    lines.extend(["## 节奏", "", "|阶段|平均结束行动值|", "|---|---:|"])
    for name,mean in phase_means(d): lines.append(f"|{name}|{mean:.1f}|")
    lines.extend(["", "前三轮目标≤700；4—6轮目标800—900；7—12轮目标≤1200。平均值按实际非幽灵战斗场数加权。", "",
        "此为当前AI策略下的模拟结果，有限样本及路线被选择的差异会影响胜率；单轮小幅变化不等于确定的因果提升。完整逐轮统计见 report.json，逐局名次和行动值见 episodes.jsonl。", ""])
    (folder/"report.md").write_text("\n".join(lines),encoding="utf-8",newline="\n")
    return d

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("runs",nargs="+")
    args=parser.parse_args()
    reports=[render(ROOT/"research"/r) for r in args.runs]
    if len(reports)!=2: return
    before,after=reports
    lines=["# 两轮测试对比与本轮调整", "", "两轮各1000场完整四AI赛事，中间只进行一次数值调整；第二轮之后未再改动平衡数值。两轮沿用相同随机种子和AI模型。", ""]
    adjustments=json.loads((ROOT/"research"/args.runs[0]/"adjustments.json").read_text(encoding="utf-8"))
    lines.extend(["## 数值调整", "", adjustments["rationale"], "", "|卡牌|属性|调整前|调整后|", "|---|---|---:|---:|"])
    for c in adjustments["changes"]: lines.append(f"|{c['name']}|{c['field']}|{c['old']}|{c['new']}|")
    for key,title in [("element_ranking","元素排名"),("route_ranking","路线排名")]:
        first={r['name']:r for r in before[key]}
        lines.extend(["",f"## {title}","","|第二轮排名|元素/路线|首轮分数|第二轮分数|首轮夺冠率|第二轮夺冠率|第二轮选择次数|","|---:|---|---:|---:|---:|---:|---:|"])
        for i,b in enumerate(after[key],1):
            a=first[b['name']]
            lines.append(f"|{i}|{ELEMENTS.get(b['name'],b['name'])}|{a['score']:+.1f}|{b['score']:+.1f}|{a['win_rate']:.1%}|{b['win_rate']:.1%}|{b['selections']}|")
    lines.extend(["","## 节奏对比","","|阶段|首轮平均行动值|第二轮平均行动值|","|---|---:|---:|"])
    for (label,a),(_,b) in zip(phase_means(before),phase_means(after)):
        lines.append(f"|{label}|{a:.1f}|{b:.1f}|")
    lines.extend(["","附：同目录 report.md、report.json、cards.snapshot.json；首轮目录含 adjustments.json。统计规则与旧脚本修正详见两轮报告。",""])
    (ROOT/"research"/args.runs[1]/"comparison.md").write_text("\n".join(lines),encoding="utf-8",newline="\n")

if __name__=="__main__": main()
