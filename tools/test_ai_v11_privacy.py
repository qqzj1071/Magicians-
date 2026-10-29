"""Opponent hidden data must not affect research combat priors."""
import json,sys
from dataclasses import asdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/round_robin'))
import train_v11_small_steps as T

def main():
 pointer=json.loads((ROOT/'docs/ai/current-tournament.json').read_text(encoding='utf-8-sig'))
 model=T.model(json.loads((ROOT/pointer['model']).read_text(encoding='utf-8')))
 cards=T.I.J.C
 cards.DECKS['privacy-own']=dict(element='fire',route='',specialization_selected=False,entries=[])
 cards.DECKS['privacy-enemy']=dict(element='fire',route='',specialization_selected=False,entries=[{'name':'火花'}])
 before=asdict(model.combat.policy('privacy-own','privacy-enemy',1))
 cards.DECKS['privacy-enemy'].update(element='poison',entries=[{'name':'毒甲'}])
 after=asdict(model.combat.policy('privacy-own','privacy-enemy',1))
 assert before==after,'Hidden target/deck affected policy'
 assert cards.DECKS['privacy-enemy']['element']=='poison','Sanitization failed to restore simulator state'
 cards.DECKS['privacy-enemy']['specialization_selected']=True
 visible=asdict(model.combat.policy('privacy-own','privacy-enemy',1))
 assert visible!=before,'Public specialization must remain available to the prior'
 print('RESEARCH_OPPONENT_HIDDEN_MUTATION_INVARIANT_OK')
if __name__=='__main__':main()
