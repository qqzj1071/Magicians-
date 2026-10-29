"""AI-only valuation adapter; never changes combat state or hidden observations."""
from dataclasses import replace
_INSTALLED=False

def bind(model, config=None):
 global _INSTALLED
 import strategic_tournament_ai as I
 E=I.J.E
 if not _INSTALLED:
  previous_value=E.value
  previous_policy=I.Combat.policy
  def value(states,i,t,policy):
   base=previous_value(states,i,t,policy)
   s=states[i];weight=getattr(policy,'resource_projection',0.0)
   if weight and s.spec and s.route=='灰烬循环':
    next_draw=(t//100+1)*100
    credit=s.ash_credit+(s.ember if s.next_fire<next_draw else 0)
    usable=min(int(E.param('ash_resource_cap',3)),credit)
    base+=weight*usable*(policy.draw+policy.energy)*100/(100+next_draw-t)
   return base
  def policy(self,*args,**kwargs):
   p=previous_policy(self,*args,**kwargs)
   if hasattr(p,'resource_projection'):
    p=replace(p,resource_projection=getattr(self,'v11_resource_projection',0.0))
   return p
  E.value=value;I.Combat.policy=policy;_INSTALLED=True
 model.combat.v11_resource_projection=float((config or {}).get('resource_projection',0))
 return model
