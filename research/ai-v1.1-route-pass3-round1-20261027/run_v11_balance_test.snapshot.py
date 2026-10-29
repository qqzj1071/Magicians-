"""Run the requested v1.1 four-AI balance sample and score elements/routes."""
from __future__ import annotations

import argparse
import copy
import json
import statistics
import hashlib
import os
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def compact_episode(ep):
    by_pid = {}
    for player in ep["eliminated"]:
        by_pid[player['pid']] = {**player, '_phase': player['eliminated_round']}
    for player in ep["champions"]:
        # The simulator also returns the final eliminated players in champions
        # when everyone dies. Deduplicate them; rank by elimination time and HP.
        if player['pid'] not in by_pid:
            by_pid[player['pid']] = {**player, '_phase': ep['end_round'] + 1}
    players = sorted(by_pid.values(), key=lambda p: (-p['_phase'], -p['tournament_hp'], p['pid']))
    assert len(players) == 4, 'A tournament must contain four unique players'
    # Equal post-settlement tournament health in one elimination round is a tie;
    # share the points for the occupied rank slots.
    points = (3, 1, -1, -3)
    placements = []
    pos = 0
    while pos < len(players):
        group = [players[pos]]
        while pos + len(group) < len(players):
            other = players[pos + len(group)]
            if (other["_phase"], other.get("tournament_hp", 0)) != (
                group[0]["_phase"], group[0].get("tournament_hp", 0)
            ):
                break
            group.append(other)
        earned = sum(points[pos : pos + len(group)]) / len(group)
        for player in group:
            placements.append(
                {
                    "pid": player["pid"],
                    "placement": pos + 1,
                    "points": earned,
                    "spec": player.get("spec", ""),
                    "route": player.get("route", ""),
                    "tournament_hp": player.get("tournament_hp", 0),
                    "eliminated_round": player.get("eliminated_round"),
                    "win_share": 1 / len(group) if pos == 0 else 0,
                }
            )
        pos += len(group)
    assert abs(sum(p['points'] for p in placements)) < 1e-9
    assert abs(sum(p['win_share'] for p in placements) - 1) < 1e-9

    battles = []
    for row in ep["rounds"]:
        for battle in row["battles"]:
            if not battle.get("ghost"):
                battles.append({"round": row["round"], "action_value": battle["result"]["time"]})
    return {"index": ep["index"], "end_round": ep["end_round"], "placements": placements, "battles": battles}


def worker(job):
    indices, checkpoint, table_path, cfg_path, namespace = job
    import tournament_inference as TI
    import survival_tournament as Q

    model = TI.load_model(checkpoint)
    table = TI.load_table(table_path)
    cfg = json.loads(Path(cfg_path).read_text(encoding="utf-8"))
    output = []
    for index in indices:
        episode = Q.simulate(
            "v11-balance",
            index,
            copy.deepcopy(model),
            table,
            cfg,
            False,
            namespace,
        )
        output.append(compact_episode(episode))
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--run", default="ai-v1.1-balance-20261027")
    parser.add_argument("--seed-namespace", help="Reuse across the two balance rounds for comparable RNG")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    os.environ.setdefault('MAGICIANS_CARD_LIBRARY', str(ROOT / 'decks/trained-v1.1-poison.json'))
    import cards as C
    assert C.CARD_VERSION == '1.1', 'Balance tests require the v1.1 library'

    out = ROOT / "research" / args.run
    out.mkdir(parents=True, exist_ok=False)
    checkpoint = (ROOT / "research" / "tournament-v1-training01" / "selected-model.json").resolve()
    table_path = (ROOT / "releases" / "deckbuilding-v1.0" / "damage.json").resolve()
    cfg_path = (ROOT / "releases" / "deckbuilding-v1.0" / "probabilities.json").resolve()
    namespace = args.seed_namespace or f"{args.run}-sealed"
    inputs = [C.CARD_LIBRARY_PATH, C.LIBRARY_PATH, checkpoint, table_path, cfg_path,
              Path(__file__), Path(__file__).with_name('engine.py')]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    (out / 'cards.snapshot.json').write_bytes(C.CARD_LIBRARY_PATH.read_bytes())
    (out / 'inputs.json').write_text(json.dumps({'namespace': namespace, 'sha256': hashes}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    batch_size = max(1, (args.games + args.workers * 4 - 1) // (args.workers * 4))
    batches = [list(range(start, min(args.games, start + batch_size))) for start in range(0, args.games, batch_size)]
    episodes = []
    jobs = []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        for batch in batches:
            jobs.append(executor.submit(worker, (batch, str(checkpoint), str(table_path), str(cfg_path), namespace)))
        for number, future in enumerate(as_completed(jobs), 1):
            episodes.extend(future.result())
            print(f"completed {number}/{len(jobs)} batches", flush=True)
    episodes.sort(key=lambda x: x["index"])
    with (out / "episodes.jsonl").open("w", encoding="utf-8") as handle:
        for episode in episodes:
            handle.write(json.dumps(episode, ensure_ascii=False) + "\n")

    element_scores = Counter()
    route_scores = Counter()
    element_counts = Counter()
    route_counts = Counter()
    element_wins = Counter()
    route_wins = Counter()
    action_values = defaultdict(list)
    for episode in episodes:
        for player in episode["placements"]:
            if player["spec"]:
                element_scores[player["spec"]] += player["points"]
                element_counts[player["spec"]] += 1
                element_wins[player['spec']] += player['win_share']
            if player["route"]:
                route_scores[player["route"]] += player["points"]
                route_counts[player["route"]] += 1
                route_wins[player['route']] += player['win_share']
        for battle in episode["battles"]:
            action_values[str(battle["round"])].append(battle["action_value"])

    def ranking(scores, counts, wins):
        return [
            {"name": name, "score": scores[name], "selections": counts[name],
             'wins': wins[name], 'win_rate': wins[name] / counts[name], 'mean_score': scores[name] / counts[name]}
            for name in sorted(scores, key=lambda name: (-scores[name], name))
        ]

    action_summary = {}
    for round_id, values in sorted(action_values.items(), key=lambda item: int(item[0])):
        action_summary[round_id] = {
            "games": len(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "p25": statistics.quantiles(values, n=4, method="inclusive")[0] if len(values) >= 2 else values[0],
            "p75": statistics.quantiles(values, n=4, method="inclusive")[2] if len(values) >= 2 else values[0],
        }
    report = {
        "version": "1.1",
        "card_library": "releases/v1.1/cards.json",
        "games": len(episodes),
        "namespace": namespace,
        "scoring": {"first": 3, "second": 1, "third": -1, "fourth": -3, "ties": "average occupied rank points"},
        "element_ranking": ranking(element_scores, element_counts, element_wins),
        "route_ranking": ranking(route_scores, route_counts, route_wins),
        'win_rate_definition': 'Tournament first-place share / selections; tied champions split one win',
        'inputs_sha256': hashes,
        'validation': {'players': sum(len(e['placements']) for e in episodes),
                       'total_points': sum(p['points'] for e in episodes for p in e['placements']),
                       'total_wins': sum(p['win_share'] for e in episodes for p in e['placements'])},
        "action_value_by_tournament_round": action_summary,
        "end_round_distribution": dict(sorted(Counter(e["end_round"] for e in episodes).items())),
    }
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == hashes[str(p.relative_to(ROOT))] for p in inputs), 'Inputs changed during the test'
    print(json.dumps({"run": str(out), "games": len(episodes), "elements": report["element_ranking"], "routes": report["route_ranking"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
