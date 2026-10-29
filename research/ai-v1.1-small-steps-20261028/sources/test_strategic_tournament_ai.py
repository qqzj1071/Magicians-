"""Information boundary, explanations, terminal credit, mixed seats and load parity."""
import copy
import json
import random
import strategic_tournament_ai as I
import survival_tournament as Q
S=Q.S


def main():
    release=S.C.ROOT/'releases/deckbuilding-v1.0'
    saved=json.loads((release/'initial-ai.json').read_text(encoding='utf-8'))
    table=json.loads((release/'damage.json').read_text(encoding='utf-8'))['table']
    cfg=json.loads((release/'probabilities.json').read_text(encoding='utf-8'))
    I.install();old=I.Learner(saved);model=copy.deepcopy(old);model.enable_training()
    p=S.Player(0,S.IDS[0]);p.current_round=1;p.tournament_hp=100;p.loss_estimate=6
    assert I.reserve_plan(p,1)>I.reserve_plan(p,0)
    p.tournament_hp=3;assert I.reserve_plan(p,2)==0
    # Public-state-only counter/target: changing another private deck must have no effect.
    players=[S.Player(i,S.IDS[i]) for i in range(4)];model.on_episode_start(players)
    for x in players:x.current_round=1;x.next_public={};x.tournament_hp=100
    I.A.pick_target(players[0],players,model.w);target=players[0].target
    players[1].deck=[(n,None) for n in S.TARGET_NAMES[S.IDS[-1]]]
    I.A.pick_target(players[0],players,model.w);assert players[0].target==target
    assert I.A.counter_value(players[0],S.names(players[0]))==0
    ep=Q.simulate('strategic-unit',0,model,table,cfg,True,'strategic-unit')
    assert ep['champions'] and model.terminal_updates==4 and model.combat.log
    assert all(len(x['seed_gains'])==2 for x in model.combat.log)
    assert all(x['own']!='ghost' for x in model.combat.log if 'own' in x)
    assert all(ledger['decision_reasons'] for row in ep['rounds'] for ledger in row['ledger'])
    restored=I.Learner(I.dump(model))
    assert restored.w==model.w and restored.combat.context==model.combat.context
    assert restored.combat.matchup==model.combat.matchup
    actors={i:copy.deepcopy(model if i%2 else old) for i in range(4)}
    mixed=Q.simulate('mixed-unit',0,copy.deepcopy(old),table,cfg,False,'mixed-unit',seat_models=actors)
    assert mixed['champions'] and all(a.combat.updates==actors[i].combat.updates for i,a in actors.items())
    print(json.dumps(dict(status='passed',learn_end=ep['end_round'],mixed_end=mixed['end_round'],combat_trials=model.combat.updates-old.combat.updates)))


if __name__=='__main__':main()
