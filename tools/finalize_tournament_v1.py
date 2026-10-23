"""Publish research inference pointer and current documentation after all audits."""
import hashlib
import json
import shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def main():
    run=ROOT/'research/tournament-v1-training01'
    analysis=json.loads((run/'analysis.json').read_text(encoding='utf-8'))
    assert json.loads((run/'audit.json').read_text(encoding='utf-8'))['status']=='passed'
    assert json.loads((run/'audit-v1.json').read_text(encoding='utf-8'))['status']=='passed'
    gain=analysis['mixed_champion_excess']
    evidence='positive' if gain['low']>0 else 'negative' if gain['high']<0 else 'uncertain'
    selected='research/tournament-v1-training01/selected-model.json'
    recommended='releases/deckbuilding-v1.0/initial-ai.json' if evidence=='negative' else selected
    profile=json.loads((ROOT/recommended).read_text(encoding='utf-8'))['construction_profile']
    pointer=dict(profile=profile,status='research_checkpoint',rule_version='deckbuilding-v1.0',
        model=recommended,selected_candidate=selected,
        model_sha256=hashlib.sha256((ROOT/recommended).read_bytes()).hexdigest(),
        release='research/tournament-v1-training01',baseline='releases/deckbuilding-v1.0/initial-ai.json',
        independent_overall_improvement_evidence=evidence,training_cycles=10,
        warning='Research controller; accepted training updates do not prove globally optimal or uniformly stronger play.')
    (ROOT/'docs/ai/current-tournament.json').write_text(json.dumps(pointer,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'docs/ai/README.md').write_text('''# 构筑与战斗AI · 当前入口

卡牌v1.0与[构筑v1.0](../../releases/deckbuilding-v1.0/README.md)冻结；AI检查点独立演进，不能回写游戏规则。

- [十轮四人赛事学习及独立终测](tournament-v1-report.md)
- [训练、回退与防过拟合方法](tournament-v1-method.md)
- [真实抓牌、存费和出牌理由示例](tournament-v1-decisions.md)
- [当前研究检查点指针](current-tournament.json)

研究候选可用tools/round_robin/tournament_inference.load_release读取research/tournament-v1-training01。实际推荐模型以current-tournament.json中的model与哈希为准；混合赛事若明确退步，保留冻结前AI作为默认。整体是否更强以独立终测与区间为准，不能用自弈胜率、训练次数或Dice代替战力。

后续训练必须换新的研究名称与种子空间；工具默认接当前推荐检查点继续学习，也可显式指定checkpoint。不覆盖本次结果，不重用终测种子调参。

冻结前策略仍保留于releases/deckbuilding-v1.0/initial-ai.json，旧构筑规则与实验已压缩且过时，默认禁止解压。固定15套标准牌组的历史战斗先验仍见[报告](training-v1/report.md)、[共性](training-v1/common.md)与[历史构筑课程](training-v1/construction.md)，不把它们作为现行赛事规则。
''',encoding='utf-8')
    p=ROOT/'README.md';text=p.read_text(encoding='utf-8')
    text=text.replace('战斗与构筑AI已完成[六轮学习](docs/ai/training-v1/report.md)，包含共性策略、120组对战档案与抓牌对照测试。当前运行牌组由decks/active.json指定，卡牌v1.0未改动。',
        '完整四人赛事AI已完成[十轮学习与独立终测](docs/ai/tournament-v1-report.md)。固定标准牌组历史六轮先验独立保留；当前标准牌组由decks/active.json指定。卡牌与构筑规则未因训练修改。')
    p.write_text(text,encoding='utf-8')
    target=run/'sources-postflight';target.mkdir(exist_ok=True);hashes={}
    for name in ['report_tournament_v1.py','audit_tournament_v1.py','train_tournament_v1.py','tournament_inference.py','verify_construction_v1.py']:
        source=ROOT/'tools/round_robin'/name;shutil.copyfile(source,target/name);hashes[name]=hashlib.sha256(source.read_bytes()).hexdigest()
    (target/'hashes.json').write_text(json.dumps(hashes,indent=2)+'\n',encoding='utf-8')
    (target/'README.md').write_text('Actual experiment executed sources/ snapshots. Postflight contains independent analysis/audit and the trainer with future-checkpoint continuation support added after this run; it does not rewrite the recorded ten-cycle results.\n',encoding='utf-8')
    for p in [ROOT/'AGENTS.md',ROOT/'README.md',ROOT/'archives/README.md',ROOT/'docs/README.md',ROOT/'tools/round_robin/README.md',*list((ROOT/'docs/ai').glob('*.md'))]:
        p.write_bytes(p.read_bytes().replace(b'\r\n',b'\n'))
    print(json.dumps(dict(status='published_research_checkpoint',evidence=evidence)))


if __name__=='__main__':main()
