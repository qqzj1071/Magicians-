"""Research adapter parity, inventory invariants, replay and reward updates."""
import copy
import json
from dataclasses import replace
import cards as C
import engine as ORIGINAL
from shared_draft_combat import ENGINE as E, battle
from simulate_shared_draft import Learner, simulate_episode, TARGETS


def main():
    ids=list(TARGETS)
    for i,a in enumerate(ids):
        b=ids[(i+4)%15]
        x=ORIGINAL.simulate(a,b,700+i,ORIGINAL.GREEDY,ORIGINAL.GREEDY,validate=True)
        y=battle(a,b,700+i,E.GREEDY,E.GREEDY)
        assert x==y,(a,b)
    states=[E.State('fire',specialization_selected=True,spec=True,energy=20),E.State('earth')]
    water=[n for n,c in C.CARDS.items() if c.element=='water' and c.rarity=='common'][:3]
    for n in water:states=E.resolve_cards(states,[E.card_plan(states,0,n,0)],0)
    assert states[0].water_layers==2 and states[0].layers==0
    assert states[0].spec and states[0].element=='fire'
    a=E.State('fire',fire_layers=2,layers=2,specialization_selected=False)
    b=replace(a,specialization_selected=True)
    assert E.fire_factor(a)-1==(E.fire_factor(b)-1)/2
    C.DECKS['mixed-legend-test']=dict(element='fire',entries=[dict(name=n) for n in ['火花','水滴','石肤','元素熔炉','魔法阵核心']])
    states=[E.State('fire',deck_id='mixed-legend-test',energy=20),E.State('earth')]
    states=E.resolve_cards(states,[E.card_plan(states,0,'元素熔炉',0)],0)
    assert states[0].layers==2 and states[0].fire_layers==2
    states=E.resolve_cards(states,[E.card_plan(states,0,'魔法阵核心',0)],0)
    assert states[0].attack_final_percent==10 and states[0].defense_final_percent==5
    before=E.stats(states,0)[0];states[0].attack+=10
    assert E.stats(states,0)[0]-before==11
    m=Learner();prior=copy.deepcopy(m.w)
    x=simulate_episode('test-replay',0,m,True)
    assert m.updates==48 and m.w!=prior
    y=simulate_episode('test-replay',0,Learner(),True)
    assert x==y
    assert x['combat_count']==24
    print(json.dumps({'mono_element_battle_parity':15,'mixed_layer_cap_and_pre_spec_rate':True,
                      'full_episode_replay':True,'both_winner_loser_updates':48,
                      'inventory_audited_after_every_purchase_phase_and_round':True}))


if __name__=='__main__':main()
