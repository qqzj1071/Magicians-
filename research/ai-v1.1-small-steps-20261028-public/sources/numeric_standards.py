"""Canonical designed mechanism values. Derived results and integer attributes are separate."""
from decimal import Decimal,ROUND_HALF_UP

def clean(value):
 d=Decimal(str(value));x=abs(d)
 if not x:return 0
 step=Decimal('.5')*Decimal(10)**x.adjusted()
 n=(d/step).quantize(Decimal(1),rounding=ROUND_HALF_UP)*step
 return int(n) if n==n.to_integral_value() else float(n)

def clean_layer(value):
 # Both selected and unselected coefficients must pass the same formatting rule.
 x=Decimal(str(value))
 if not x:return 0
 exp=abs(x).adjusted()
 candidates=[Decimal(m)/2*Decimal(10)**e for e in range(exp-1,exp+2) for m in range(2,20)]
 n=min((v for v in candidates if canonical(v/2)),key=lambda v:(abs(v-abs(x)),-v))
 return clean(n if x>0 else -n)

def canonical(value):return Decimal(str(value))==Decimal(str(clean(value)))

LAYER_KEYS=('fire_layer_percent','water_lifesteal_per_layer','earth_shield_per_layer','wind_layer_pen','poison_damage_per_layer','wind_pierce_def_per_layer')
def normalize_parameters(params):
 result={}
 for key,value in params.items():
  if isinstance(value,dict):result[key]={n:clean(v) for n,v in value.items()}
  elif key in LAYER_KEYS:result[key]=clean_layer(value)
  else:result[key]=clean(value)
 return result

def validate_grid(params):
 for key,value in params.items():
  if isinstance(value,dict):
   for n,v in value.items():assert canonical(v),(key,n,v)
  else:assert canonical(value),(key,value)
 for key in LAYER_KEYS+tuple(k for k in ('wind_pierce_shield_per_layer',) if k in params):
  assert canonical(params[key]/2),(key,'unselected',params[key]/2)
 return True

def validate(params):
 # Version 8 locks the user-specified tide bonuses.
 validate_grid(params)
 assert params['ash_resource_cap']==2
 if 'echo_heal_record_bonus_percent' in params:
  assert params['storm_tide_bonus_percent']==60
  assert params['echo_tide_bonus_percent']==30
  assert params['echo_heal_record_bonus_percent']==20
 else:
  assert params['storm_tide_bonus_percent']==80
  assert params['echo_tide_bonus_percent']==40
 return True
