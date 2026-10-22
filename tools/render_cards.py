"""Regenerate concise card views from the only authoritative frozen catalog."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
def render():
 data=json.loads((ROOT/'releases/v1.0/cards.json').read_text(encoding='utf-8'))
 for element,label in [('fire','火'),('water','水'),('earth','土'),('wind','风'),('poison','毒'),('generic','通用')]:
  lines=[f'# {label}卡牌 · v1.0','','由[唯一卡牌数据](../../releases/v1.0/cards.json)生成。固定攻防每次打出加算；首次元素层每张仅获得一次；能力牌打出后移出本场。普通增伤缩放已在本视图中折算，条件合计后取整的牌保留公式，不额外再乘。','']
  for tier,tlabel in [('specialization','专精'),('legendary','传奇'),('epic','史诗'),('rare','稀有'),('common','普通')]:
   cards=[c for c in data['cards'].values() if c['element']==element and c['rarity']==tier]
   if not cards:continue
   lines += [f'## {tlabel}（{len(cards)}）','','|卡牌|费|攻|防|首次元素层|效果|','|---|---:|---:|---:|---:|---|']
   lines += [f'|{c["name"]}|{c["cost"]}|{c["attack"]}|{c["defense"]}|{c["layers"]}|'+c['text'].replace('\n',' ').replace('|','／')+'|' for c in cards]
   lines.append('')
  (ROOT/f'docs/cards/{element}.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
if __name__=='__main__':render()
