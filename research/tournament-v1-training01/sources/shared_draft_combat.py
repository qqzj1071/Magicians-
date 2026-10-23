"""Isolated research extension; frozen engine/planner files remain unchanged.

Keeps separate ordinary elemental layers for mixed early decks. No trained
matchup profile is treated as calibrated for these new evolving decks.
"""
import sys
import types
from pathlib import Path
from dataclasses import replace
import cards as C


def build():
    source = (Path(__file__).parent / 'engine.py').read_text(encoding='utf-8')
    source = source.replace("    layers: int = 0\n", "    layers: int = 0\n" + ''.join(f'    {e}_layers: int = 0\n' for e in ['fire','water','earth','wind','poison']))
    source = source.replace("    if c.element!='generic' and name not in s.seen:\n        s.layers+=c.layers;s.seen=s.seen|{name}", """    if c.element!='generic' and name not in s.seen:
        key=c.element+'_layers'
        old=getattr(s,key)
        new=old+c.layers if c.element==s.element else min(2,old+c.layers)
        setattr(s,key,new)
        if c.element==s.element:s.layers+=new-old
        s.seen=s.seen|{name}""")
    source = source.replace("return 1+layer_rate(s,'fire_layer_percent',2.5)*s.layers/100 if s.element=='fire' else Q(1)", "return 1+element_rate(s,'fire','fire_layer_percent',2.5)*s.fire_layers/100")
    # Ordinary benefits apply to every acquired element; specialization mechanics
    # remain tied to the selected main element and played ability.
    source = source.replace("if kind=='missile' and s.element=='wind':", "if kind=='missile' and s.wind_layers:")
    source = source.replace("s.layers*(layer_rate(s,'wind_layer_pen',5)", "s.wind_layers*(element_rate(s,'wind','wind_layer_pen',5)")
    source = source.replace("if s.element=='poison' and s.layers and p.actual>0:", "if s.poison_layers and p.actual>0:")
    source = source.replace("if p.kind=='missile' and s.element=='water':", "if p.kind=='missile' and s.water_layers:")
    source = source.replace("else layer_rate(s,'water_lifesteal_per_layer',5)", "else element_rate(s,'water','water_lifesteal_per_layer',5)")
    source = source.replace("heal(s,basis*rate*s.layers/100", "heal(s,basis*rate*s.water_layers/100")
    source = source.replace("if s.element=='earth' and s.layers:", "if s.earth_layers:")
    source = source.replace("layer_rate(s,'earth_shield_per_layer',5)*s.layers", "element_rate(s,'earth','earth_shield_per_layer',5)*s.earth_layers")
    source = source.replace("snapshot[i].element=='earth' and snapshot[i].layers>0", "snapshot[i].earth_layers>0")
    source = source.replace("layer_rate(s,'poison_damage_per_layer',2.5)/100*s.layers", "element_rate(s,'poison','poison_damage_per_layer',2.5)/100*s.poison_layers")
    source = source.replace("if states[i].element=='poison' and states[1-i].poison:", "if states[i].poison_layers and states[1-i].poison:")
    source = source.replace("    return p,State(deck['element'])", "    state=State(deck['element'],specialization_selected=deck.get('specialization_selected',True))\n    return p,state")
    # A compressed deck entry's quantity must be expanded by caller (entries are
    # one physical initial copy each, consistent with the existing Fighter API).
    source = source.replace("        # All legal v5 search candidates are mono-element; neither can yield a bonus.\n        pass", """        if name=='元素熔炉':
            deck=DECKS[snapshot[i].deck_id] if hasattr(snapshot[i],'deck_id') else None
            if deck:
                foreign=sum(CARDS[x['name']].element not in ('generic',s.element) for x in deck['entries'])
                s.layers+=min(6,foreign)
                setattr(s,s.element+'_layers',getattr(s,s.element+'_layers')+min(6,foreign))
        else:
            deck=DECKS[snapshot[i].deck_id] if hasattr(snapshot[i],'deck_id') else None
            elements={CARDS[x['name']].element for x in deck['entries'] if CARDS[x['name']].element!='generic'} if deck else set()
            if len(elements)>=3:
                s.attack=ceil(s.attack*Q(10+len(elements)-2,10))
                s.defense=ceil(s.defense*Q(20+len(elements)-2,20))""")
    # Sustained stat multipliers are applied in stats(), not just once at play.
    source = source.replace("    layers: int = 0\n", "    layers: int = 0\n    deck_id: str = ''\n    attack_final_percent: int = 0\n    defense_final_percent: int = 0\n")
    source = source.replace("s.attack=ceil(s.attack*Q(10+len(elements)-2,10))", "s.attack_final_percent+=10*(len(elements)-2)")
    source = source.replace("s.defense=ceil(s.defense*Q(20+len(elements)-2,20))", "s.defense_final_percent+=5*(len(elements)-2)")
    source = source.replace("return max(0,a), max(0,d)", "return max(0,ceil(a*Q(100+s.attack_final_percent,100))), max(0,ceil(d*Q(100+s.defense_final_percent,100)))")
    source = source.replace("MERGE_SKIP = BOOL_FIELDS | {", "MERGE_SKIP = BOOL_FIELDS | {'deck_id',")
    source = source.replace("state=State(deck['element'],specialization_selected", "state=State(deck['element'],deck_id=deck_id,specialization_selected")
    module = types.ModuleType('shared_draft_engine')
    module.__file__ = str(Path(__file__).parent / 'engine.py')
    sys.modules[module.__name__] = module
    exec(compile(source, module.__file__, 'exec'), module.__dict__)
    module.element_rate = lambda s, element, name, default: module.param(name, default) * (1 if s.specialization_selected and s.element == element else module.Q(1,2))
    original = module.card_plan

    def card_plan(snapshot, i, name, t):
        if C.CARDS[name].element in ('generic', snapshot[i].element):
            return original(snapshot, i, name, t)
        # Foreign ordinary cards cannot activate another element's exclusive
        # mechanics just because the main specialization has been played.
        altered = [replace(s) for s in snapshot]
        altered[i].spec = False
        altered[i].route = ''
        plan = original(altered, i, name, t)
        plan.local[i].spec = snapshot[i].spec
        plan.local[i].route = snapshot[i].route
        return plan

    module.card_plan = card_plan
    return module


ENGINE = build()


def battle(a, b, seed, policy_a=None, policy_b=None, validate=True):
    """Use public baseline greedy controller; no stale fixed-deck matchup claim."""
    return ENGINE.simulate(a,b,seed,policy_a or ENGINE.BASELINE,policy_b or ENGINE.BASELINE,validate=validate)
