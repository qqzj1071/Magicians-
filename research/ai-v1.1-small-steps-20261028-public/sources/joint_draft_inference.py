"""Load the reviewed joint checkpoint and explicit route-feasibility rules."""
import json
from pathlib import Path
import route_feasible_draft as R


def load_model(checkpoint):
    checkpoint=Path(checkpoint);data=json.loads(checkpoint.read_text(encoding='utf-8'))
    R.install();model=R.T.JointLearner();model.w=data['draft']
    model.combat.stage=data['combat']['stage'];model.combat.route=data['combat']['route']
    model.combat.updates=data['combat']['updates'];model.combat.accepts=data['combat']['accepts']
    model.combat.experience.update(data['combat']['experience'])
    return model
