"""Reproduce the experimental banking candidate; final regression, not a default."""
import json
from pathlib import Path
import public_saving_draft as N


def load_model(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('construction_profile')!='public-saving-v1':raise ValueError('Expected public-saving-v1 checkpoint')
    N.install();model=N.Learner();model.w=data['draft'];model.updates=data['draft_updates']
    c=data['combat'];model.combat.stage=c['stage'];model.combat.route=c['route']
    model.combat.updates=c['updates'];model.combat.accepts=c['accepts'];model.combat.experience.update(c['experience'])
    return model
