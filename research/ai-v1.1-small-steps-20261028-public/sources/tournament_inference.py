"""Load a survival-v6 research checkpoint and validated damage schedule."""
import json
import hashlib
from pathlib import Path
import survival_tournament as Q


def load_model(checkpoint):
    data=json.loads(Path(checkpoint).read_text(encoding='utf-8'))
    if data.get('construction_profile')=='tournament-v1':
        import strategic_tournament_ai as I
        I.install();model=I.Learner(data)
        if Q.S.C.CARD_VERSION=="1.1":
            from ai_v11_policy import bind
            bind(model,data.get("ai_v11",{}))
        return model
    if data.get('construction_profile')!='survival-v6':raise ValueError('Expected survival-v6 or tournament-v1 checkpoint')
    Q.A.install();model=Q.A.Learner(data);model.w=data['draft'];model.prior=data['prior'];model.updates=data['updates']
    return model


def load_table(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'));table=data.get('table',data)
    Q.validate_table(table);return table


def load_release(root):
    root=Path(root);selection_path=root/('recommendation.json' if (root/'recommendation.json').exists() else 'release-selection.json')
    selection=json.loads(selection_path.read_text(encoding='utf-8'))
    folder=root/selection['chosen_folder'];checkpoint=folder/'selected-model.json';schedule=folder/'selected-table.json'
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest()==selection['model_sha256']
    assert hashlib.sha256(schedule.read_bytes()).hexdigest()==selection['table_sha256']
    return load_model(checkpoint),load_table(schedule),json.loads((folder/'config.json').read_text(encoding='utf-8'))
