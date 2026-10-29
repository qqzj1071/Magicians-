import copy,unittest
from dataclasses import replace
from learning_core import *
from learning_jobs import shrink

class Learning(unittest.TestCase):
 def ctx(self):return dict(decks=copy.deepcopy(C.DECKS),initial_decks=copy.deepcopy(C.DECKS),common={},routes={},pairs={})
 def test_all_reference_decks_legal_and_proposals(self):
  ctx=self.ctx()
  for a,d in ctx['decks'].items():
   self.assertTrue(legal(d),a)
   proposals,moves=candidate_decks(ctx,a,1,[b for b in IDS if b!=a][:3],{})
   self.assertEqual(len(proposals),len(moves)+1)
   for p in proposals:self.assertTrue(legal(p))
 def test_seed_partitions(self):
  values=[seed(stage,r,a,b,k) for stage in ('route-train','route-valid','feedback','final','factorial-final') for r in (1,2,99) for a,b in PAIRS for k in range(4)]
  self.assertEqual(len(values),len(set(values)))
 def test_common_is_shared_and_mirror_is_symmetric(self):
  c=self.ctx();c['common']={'core_priority':123};c['routes'][IDS[0]]=asdict(P.initial(IDS[0],IDS[1]))
  self.assertEqual(base_policy(c,IDS[0],IDS[1]).core_priority,123)
  p=base_policy(c,IDS[0],IDS[0]);self.assertEqual(p,policy(c,IDS[0],IDS[0]))
 def test_shrink_is_bounded(self):
  a=P.Policy(damage=3);b=P.Policy(damage=1);self.assertEqual(shrink(a,b,.5).damage,2)
 def test_deterministic_seat_exchange(self):
  a,b=IDS[0],IDS[4];pa,pb=P.initial(a,b),P.initial(b,a)
  x=game(a,b,998721,pa,pb,False,True);y=game(a,b,998721,pa,pb,True,True)
  self.assertEqual(x['winner'],y['winner']);self.assertEqual(x['players'],y['players'])
 def test_optional_lookahead_still_uses_affordable_public_pool(self):
  states=[E.State('fire',energy=3),E.State('earth')]
  pool=['炽焰王冠','火花','压实火药'];p=replace(P.initial('fire-01','earth-01'),combo=.15,reserve=.3,cleanse=1)
  q,_=P.choose(states,0,pool,p,0);self.assertEqual(len(q),len(set(q)))
  st=states
  for n in q:
   self.assertLessEqual(C.CARDS[n].cost,st[0].energy);st=E.resolve_cards(st,[E.card_plan(st,0,n,0)],0)

if __name__=='__main__':unittest.main()
