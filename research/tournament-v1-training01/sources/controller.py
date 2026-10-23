"""Runtime entry: load a validated matchup profile, otherwise explicit route prior."""
import json
import hashlib
from dataclasses import replace
from pathlib import Path
from functools import lru_cache
from cards import ROOT,LIBRARY_PATH,CARD_LIBRARY_PATH
import planner as P
import engine as E


@lru_cache(maxsize=4)
def library(path):
    return json.loads(path.read_text(encoding='utf-8'))


def policy_for(own,opponent,path=None,layer='matchup'):
    path=path or ROOT/'tools/round_robin/policies.json'
    registry=library(path)
    if registry.get('rule_version')!=E.RULE_VERSION:
        raise ValueError('AI knowledge rule version differs from the current battle engine; retrain or load a matching version.')
    expected=registry.get('deck_library_sha256')
    if expected and hashlib.sha256(LIBRARY_PATH.read_bytes()).hexdigest()!=expected:
        raise ValueError('Card numbers or deck lists changed after calibration; validate and retrain before using these policies.')
    for module,key in ((E,'engine_sha256'),(P,'planner_sha256')):
        expected=registry.get(key)
        if expected and hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()!=expected:
            raise ValueError('Battle or planner code changed after calibration; revalidate these policies.')
    expected=registry.get('card_library_sha256')
    if expected and hashlib.sha256(CARD_LIBRARY_PATH.read_bytes()).hexdigest()!=expected:
        raise ValueError('Frozen v1.0 cards changed after calibration.')
    if layer not in ('common','route','matchup'):
        raise ValueError('Policy layer must be common, route or matchup.')
    entry=registry['matchups'].get('|'.join(sorted((own,opponent))))
    if entry and layer=='matchup':return P.Policy(**entry['policies'][own])
    p=P.initial(own,opponent)
    if layer!='common' and own in registry.get('routes',{}):
        p=replace(p,**{k:v for k,v in registry['routes'][own].items() if k not in ('own','opponent')})
    p=replace(p,**registry.get('common',{}))
    return replace(p,own=own,opponent=opponent)


def choose(snapshot,player,pool,t,discard,own,opponent,path=None):
    return P.choose(snapshot,player,pool,policy_for(own,opponent,path),t,discard)


def battle(own,opponent,seed,trace=False,validate=False):
    return E.simulate(own,opponent,seed,policy_for(own,opponent),policy_for(opponent,own),
                      trace=trace,validate=validate)
