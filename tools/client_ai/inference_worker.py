"""Inference-only JSONL adapter. Receives sanitized observations, never live game state.

Frozen research sources and checkpoints are imported unchanged. The C# engine
remains authoritative; research projections are advice, not game simulation.
"""
import os
import hashlib
import json
import random
import sys
import traceback
from dataclasses import fields
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ["MAGICIANS_CARD_LIBRARY"] = str(ROOT / "decks/trained-v1.1-poison.json")
sys.path.insert(0, str(ROOT / "tools/round_robin"))
import strategic_tournament_ai as I
import tournament_inference as inference

POINTER = json.loads((ROOT / "docs/ai/current-tournament.json").read_text(encoding="utf-8-sig"))
CHECKPOINT = ROOT / POINTER["model"]
MODEL_HASH = hashlib.sha256(CHECKPOINT.read_bytes()).hexdigest()
if MODEL_HASH != POINTER["model_sha256"]:
    raise ValueError("Recommended AI checkpoint hash mismatch")
MODEL = inference.load_model(CHECKPOINT)
BOUND_ACTOR = None
STYLE_ID = os.environ.get("MAGICIANS_AI_STYLE", "")
STYLES = json.loads((ROOT / "Data/AI/single-player-styles.json").read_text(encoding="utf-8"))["profiles"]
STYLE = next((s for s in STYLES if s["id"] == STYLE_ID), None)
if STYLE_ID and STYLE is None:
    raise ValueError("Unknown single-player AI style")
if STYLE:
    for key, factor in STYLE["draft"].items():
        if key in MODEL.w: MODEL.w[key] *= factor
S, T, J = I.A.T.S, I.A.T, I.J
E, C = J.E, S.C
CARD_HASH = hashlib.sha256(C.CARD_LIBRARY_PATH.read_bytes()).hexdigest()
if C.CARD_LIBRARY_PATH.resolve() != (ROOT / "releases/v1.1/cards.json").resolve():
    raise ValueError("Client inference must use the authoritative v1.1 card library")


def draft(view):
    public = view["publicPlayers"]
    index = next(i for i, p in enumerate(public) if p["id"] == view["player"])
    own_public = public[index]
    affinities = sorted(k for k, v in S.TARGETS.items() if not STYLE or not STYLE["element"] or v["element"] == STYLE["element"])
    affinity = affinities[int(hashlib.sha256(STYLE_ID.encode()).hexdigest()[:8], 16) % len(affinities)] if STYLE else sorted(S.TARGETS)[0]
    p = S.Player(index, affinity)
    p.deck = [(c["name"], c["id"]) for c in view["deck"]]
    p.spec, p.current_round, p.points = view["spec"], view["round"], view["points"]
    p.free_used = view["freeUsed"]
    p.economy = "growth-v4"
    p.tournament_hp = own_public["life"]
    p.loss_estimate = view["lossEstimate"]
    p.streak = view["winStreak"] or -view["lossStreak"]
    p.explanations = []
    p.public_market = {"players": {str(i): dict(spec=q["spec"], route=q["route"]) for i, q in enumerate(public)}, "release_round": {}}
    MODEL.public = p.public_market
    p.next_public = next((dict(spec=q["spec"], route=q["route"]) for q in public if q["id"] == view["nextOpponent"]), {})
    tokens = {o["slot"]: o["name"] for o in view["offers"]}
    from types import SimpleNamespace
    p.visible_route_pool = SimpleNamespace(offers={index: list(tokens)}, tokens=tokens)
    p.refresh_slots = len(tokens)
    I.A.pick_target(p, [], MODEL.w)
    ns = S.names(p)
    before = I.vector(p, ns)
    buys, removals = [], []
    for action in view["legalActions"]:
        kind, cost = action["kind"], action["cost"]
        after = list(ns)
        if kind == "buy":
            native_cost, native_old = T.A.price(p, action["card"], MODEL.w, [])
            replacement_name = next((c["name"] for c in view["deck"] if c["id"] == action.get("replace")), None)
            if native_cost is None or native_cost != cost or native_old != replacement_name:
                continue
            if action.get("replace"):
                after.remove(next(c["name"] for c in view["deck"] if c["id"] == action["replace"]))
            after.append(action["card"])
            after = T.A.projected(p, after)
        elif kind == "remove":
            after.remove(next(c["name"] for c in view["deck"] if c["id"] == action["card"]))
        else:
            continue
        vector = I.vector(p, after)
        features = {k: vector[k] - before[k] for k in before}
        features["coin"] = -cost
        features["bank"] = I.A.bank_value(p, p.points - cost) - I.A.bank_value(p, p.points)
        if kind == "buy":
            features["next_counter"] *= 1 + max(0, 1 - p.tournament_hp / 50)
            features["tempo_streak"] = features["specialization_jump"] * .2 * int(abs(p.streak) % 3 == 2)
        MODEL.payment_features(p, features, cost)
        score = T.A.dot(MODEL.w, features)
        (buys if kind == "buy" else removals).append((score, action, features))
    def best(rows):
        return max(rows, key=lambda x: (x[0], x[1].get("card") or "", x[1].get("slot") or "")) if rows else None
    chosen = best(buys)
    if chosen and chosen[0] > .025:
        return dict(action=chosen[1], score=chosen[0], reason="trained_positive_purchase", target=p.target, features=chosen[2])
    refresh = next((a for a in view["legalActions"] if a["kind"] == "refresh"), None)
    if refresh:
        features, accepted = MODEL.refresh_decision(p, [], p.current_round, random.Random(0), False)
        if accepted:
            return dict(action=refresh, reason="trained_expected_refresh_value", features=features, target=p.target)
    chosen = best(removals)
    if chosen and chosen[0] > .025:
        return dict(action=chosen[1], score=chosen[0], reason="trained_positive_removal", features=chosen[2], target=p.target)
    return dict(action={"kind": "finish", "cost": 0}, reason="trained_hold_and_bank", target=p.target)


ALIASES = {
    "Life": "hp", "Attack": "attack", "Defense": "defense", "Shield": "shield", "Energy": "energy", "NextFire": "next_fire",
    "Embers": "ember", "Tides": "tide", "UnredeemedEmbersSpent": "spent_ember", "ShuffleCount": "shuffles",
    "AshCyclePendingCredit": "ash_credit", "NextTideHealingRecordBonusPercent": "tide_record_bonus",
    "AshRebirthUsed": "ash_rebirth_claims", "TemperBonusUses": "ash_return_claims",
    "NextDrawBonus": "next_draw", "NextEnergyBonus": "next_energy", "NextGapAdjustment": "delay",
    "AttackIntervalModifier": "permanent_delay", "NextMissileBonusPercent": "bonus", "NextMissileBonusFlat": "extra",
    "ShieldDecayDamage": "shield_loss", "ShieldDecayBonus": "grip_bonus", "NextDefensePenetrationPercent": "def_pen",
    "WindMainShotCount": "shot_count", "LastMainMissileActionValue": "last_time", "LastMainMissileActualDamage": "last_main",
    "WindTraceLayers": "wind_marks", "PoisonLayers": "poison", "NextPoisonDecayActionValue": "poison_due",
    "PoisonDecayIntervalPercent": "decay_extend", "PoisonDecayProtectionCharges": "poison_guards",
    "NextPoisonOnHitLayers": "poison_next_hit", "ExtraPoisonTickCharges": "poison_repeat",
    "NextIncomingDamageFlat": "reduce_flat", "ShieldBrokenThisBattle": "shield_broken", "ShieldBreakReturnFlat": "return_flat",
    "NextMissileHealingPercent": "heal_hit80", "MainDamageBonusUntilDrawPercent": "window_bonus",
    "MainShieldPenetrationUntilDrawPercent": "window_pen", "MainDefensePenetrationPercent": "main_def_pen",
    "NextMainTemporaryShieldPercent": "pre_shield", "WarGodEmblemActive": "badge", "GuardianBarrierActive": "guardian"
}


def register_deck(key, names, element, route, selected):
    C.DECKS[key] = dict(id=key, element=element, route=route, specialization_selected=selected,
                        entries=[dict(name=n, quantity=1) for n in names])


def visible_state(resources, element, selected, route, deck_id, seen=()):
    if element not in ("fire", "water", "earth", "wind", "poison"):
        element = max(("fire", "water", "earth", "wind", "poison"), key=lambda e: resources.get(e.title() + "Layers", 0))
    state = E.State(element, specialization_selected=bool(selected), deck_id=deck_id)
    for old, new in ALIASES.items():
        if old in resources:
            setattr(state, new, resources[old])
    for e, key in (("fire", "FireLayers"), ("water", "WaterLayers"), ("earth", "EarthLayers"), ("wind", "WindLayers"), ("poison", "PoisonEnchantmentLayers")):
        setattr(state, e + "_layers", resources.get(key, 0))
    state.layers = getattr(state, element + "_layers")
    state.spec = bool(resources.get({"fire": "EmberDamageActive", "water": "TideActive", "earth": "EarthBarrierActive", "wind": "WindGaleActive", "poison": "PlagueActive"}[element], False))
    state.route = route if resources.get("RouteActivated", False) else ""
    state.seen = frozenset(seen)
    state.interval_factor = Fraction(str(resources.get("PermanentIntervalMultiplierPercent", 100))) * Fraction(str(resources.get("TemporaryIntervalMultiplierPercent", 100))) / 10000
    state.shield_loss = Fraction(str(resources.get("ShieldDecayDamage", 0))) / 3
    state.tide_bonus = max(0, resources.get("NextTideDamageMultiplierPercent", 100) - 100)
    if state.route == "生命之泉": state.main_def_pen = max(0, state.main_def_pen - 20)
    state.negative_guard = int(resources.get("NegativeSuppressedUntilActionValue", 0) > resources.get("ObservationTime", 0))
    state.heal_block = resources.get("HealingReductionPercent", 0) if resources.get("HealingReductionUntilActionValue", 0) > resources.get("ObservationTime", 0) else 0
    multiplier = resources.get("NextIncomingDamageMultiplierPercent", 100)
    state.reduce_percent = max(0, 100 - multiplier)
    state.vulnerability = max(0, multiplier - 100)
    state.subs = tuple((resources.get("NextWindSubmissileFlat", 18) or 18,
                        resources.get("NextWindSubmissileAttackPercent", 20) or 20, 1)
                       for _ in range(resources.get("PendingWindSubmissiles", 0)))
    state.subs += tuple((15, 20, 0) for _ in range(resources.get("PendingSubmissiles", 0)))
    if not state.poison_due:
        state.poison_due = E.INF
    return state


def combat_context(view):
    own_element = view["ownSpec"] or max(("fire", "water", "earth", "wind", "poison"), key=lambda e: sum(C.CARDS[n].layers for n in view["ownDeck"] if C.CARDS[n].element == e))
    enemy_element = view["opponentSpec"] or "earth"
    # The opponent registration is an intentionally empty public prior, augmented
    # only with their announced specialization and route. Never their actual deck.
    enemy_names = [n for n, c in C.CARDS.items() if c.kind == "specialization" and c.element == view["opponentSpec"]]
    if view["opponentRoute"]:
        enemy_names.append(view["opponentRoute"])
    register_deck("client-self", view["ownDeck"], own_element, view["ownRoute"], view["ownSpec"])
    register_deck("client-public-enemy", enemy_names, enemy_element, view["opponentRoute"], view["opponentSpec"])
    policy = MODEL.combat.policy("client-self", "client-public-enemy", view["round"])
    if STYLE:
        from dataclasses import replace
        policy = replace(policy, **{k: getattr(policy, k) * factor for k, factor in STYLE["combat"].items()})
    snapshot = [visible_state(view["self"], own_element, view["ownSpec"], view["ownRoute"], "client-self", view["ownPlayed"]),
                visible_state(view["opponent"], enemy_element, view["opponentSpec"], view["opponentRoute"], "client-public-enemy")]
    # The client expires poison on its window boundary. An observed due marker
    # may therefore be overdue; project it at the current legal event boundary.
    for state in snapshot:
        state.next_fire = max(view["actionValue"], state.next_fire)
        state.poison_due = max(view["actionValue"], state.poison_due) if state.poison else E.INF
    return policy, snapshot


def combat(view):
    policy, snapshot = combat_context(view)
    # One committed action, then reobserve the real C# state. No future draw is read.
    queue, reasons = J.P.choose(snapshot, 0, [c["name"] for c in view["hand"]], policy, view["actionValue"], view["ownDiscard"])
    if not queue:
        return dict(kind="end", reason="trained_no_positive_legal_card")
    selected = next(c for c in view["hand"] if c["name"] == queue[0])
    return dict(kind="play", card=selected["id"], reason=reasons[0])


def search(view):
    # This request exists only after a specific search card was committed to play.
    # Reuse the original trained planner on each revealed candidate, as the
    # reference search controller does; never enumerate or sample a hidden pile.
    context = view["combatContext"]
    policy, snapshot = combat_context(context)
    snapshot = E.resolve_cards(snapshot, [E.card_plan(snapshot, 0, view["sourceCard"], context["actionValue"])], context["actionValue"])
    snapshot[0].energy = 3
    result = []
    for candidate in view["candidates"]:
        queue, reasons = J.P.choose(snapshot, 0, [candidate["name"]], policy, context["actionValue"], context["ownDiscard"])
        result.append((reasons[0]["score"] if queue else -100000, candidate["id"]))
    return dict(targets=[identity for _, identity in sorted(result, reverse=True)[:view["maximumSelections"]]], reason="revealed_candidates_only")


def handle(request):
    kind = request["kind"]
    if kind == "metadata":
        return dict(model=POINTER["model"], modelHash=MODEL_HASH, mode="inference_only", planner=J.P.PLANNER_VERSION, style=STYLE_ID)
    return {"draft": draft, "combat": combat, "search": search}[kind](request["view"])


for line in sys.stdin:
    try:
        request = json.loads(line)
        if request["kind"] != "metadata":
            view_actor = (request["view"]["combatContext"] if request["kind"] == "search" else request["view"])["player"]
            if request["actor"] != view_actor:
                raise ValueError("Observation owner does not match inference participant")
            if BOUND_ACTOR is None:
                BOUND_ACTOR = request["actor"]
            if request["actor"] != BOUND_ACTOR:
                raise ValueError("An inference worker may serve only its bound participant")
        response = dict(ok=True, result=handle(request), modelHash=MODEL_HASH, cardHash=CARD_HASH)
    except Exception as error:
        traceback.print_exc(file=sys.stderr)
        response = dict(ok=False, error=str(error), modelHash=MODEL_HASH)
    print(json.dumps(response, ensure_ascii=False, allow_nan=False), flush=True)
