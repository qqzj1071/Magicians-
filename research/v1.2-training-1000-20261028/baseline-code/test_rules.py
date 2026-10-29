"""Numeric/transaction regressions plus an explicit all-card execution sweep."""
from collections import Counter
from copy import deepcopy
from fractions import Fraction as Q
import random
import json
import unittest
from .catalog import CARDS, ELEMENTS, SPECIAL, START, START_ONLY, copies
from .effects import EFFECTS, verify_registry
from .engine import Battle
from .model import Modifier
from .model import PlannedCard
from .policy import TARGETS
from .tournament import Player, base_income, free_price, price_and_replace, templates
from .pool import Pool

def fixture(name, others=(), opponent='攻击强化', rich=False):
    b=Battle(([name,*others],[opponent,'防御强化','护盾']),seed=19,trace=True)
    for i,s in enumerate(b.players):
        s.pile=list(s.instances)
        s.hand=[s.pile.pop(0)];s.stage=1;s.energy=100
    if rich:
        s,e=b.players;s.hp=400;s.shield=250;e.shield=150;e.poison=6
        element=CARDS[name].element
        s.specialization=element if element in ELEMENTS else 'fire'
        for el in ELEMENTS:s.layers[el]=5
        s.active.add(SPECIAL[s.specialization]);s.ember=3 if s.specialization=='fire' else 0
        s.active.add({'fire':'灰烬循环','water':'潮汐回响','earth':'大地之握','wind':'风痕','poison':'蚀骨'}[s.specialization])
        s.tide=75 if s.specialization=='water' else 0
    return b

def play(b,i=0):
    b.card_step({i:b.players[i].hand[0].uid})
    return b.players[i]

class CoverageTests(unittest.TestCase):
    def test_registry_has_every_current_card(self):
        self.assertEqual(verify_registry(),239)
        self.assertEqual(set(EFFECTS),set(CARDS))

    def test_every_card_executes_dry_and_rich_without_old_dispatch(self):
        for name in CARDS:
            for rich in (False,True):
                with self.subTest(name=name,rich=rich):
                    b=fixture(name,('火花','掠影','护盾','短促'),rich=rich)
                    s=b.players[0]
                    # Include legal recycle targets in the discard zone.
                    inst=s.pile.pop();s.discard.append(inst)
                    old_seen=set(s.seen)
                    s=play(b)
                    self.assertEqual(b.executed[name],1)
                    self.assertTrue(old_seen<=s.seen)
                    self.assertEqual(any(x.name==name for x in s.removed),CARDS[name].ability)
                    for p in b.players:p.assert_instances()

class DeckOperationTests(unittest.TestCase):
    def test_initial_cards_are_not_pool_tokens(self):
        pool=Pool()
        self.assertEqual(len(pool.tokens),912)
        self.assertFalse(START_ONLY & set(pool.tokens.values()))
        self.assertTrue(all(copies(CARDS[n])==0 for n in START))

    def test_generated_boards_exclude_starters_and_conserve_inventory(self):
        rng=random.Random(5);pool=Pool();players=[Player(i,ELEMENTS[i]) for i in range(4)]
        for r in range(1,21):
            pool.begin();faces=templates(players,r,rng)
            pool.generate(players,faces[0],r,0,rng)
            for board in pool.offers.values():
                self.assertFalse(START_ONLY & {pool.tokens[t] for t in board if t})
            pool.audit(players)
            for p in players:pool.release(p.pid)

    def test_existing_route_has_one_new_route_across_both_faces_in_rounds_10_12(self):
        for r in (10,12):
            p=Player(0,'fire');p.spec='fire'
            p.deck += [(n,None) for n in ('炽焰王冠','灰烬循环','火花','引火','燃页')]
            pool=Pool();pool.begin();rng=random.Random(r)
            ranks={0:[3]*8};pool.generate([p],ranks,r,0,rng)
            first={pool.tokens[t] for t in pool.offers[0] if t and CARDS[pool.tokens[t]].kind=='route_legendary'}
            pool.release(0);pool.generate([p],ranks,r,1,rng,bought={0:set()})
            second={pool.tokens[t] for t in pool.offers[0] if t and CARDS[pool.tokens[t]].kind=='route_legendary'}
            self.assertLessEqual(len(first|second),1)
            pool.audit([p])

    def test_all_fifteen_ai_targets_are_valid_current_decks(self):
        self.assertEqual(len(TARGETS),15)
        for deck in TARGETS.values():
            names=deck['entries'];counts=Counter(names)
            self.assertTrue(set(names)<=CARDS.keys())
            self.assertEqual(sum(CARDS[n].kind=='route_legendary' for n in names),1)
            self.assertLessEqual(sum(CARDS[n].rarity=='legendary' for n in names),3)
            self.assertTrue(all(k<=1 or n in ('攻击强化','防御强化') and k<=2 for n,k in counts.items()))

    def test_random_return_preserves_existing_order_and_instances(self):
        positions=set()
        for seed in range(60):
            b=fixture('换页',('火花','润泽','掠影','护盾'))
            s=b.players[0];s.rng.seed(seed)
            original=[x.uid for x in s.pile]
            returned=s.hand.pop();b.random_insert(s,[returned])
            self.assertEqual([x.uid for x in s.pile if x.uid!=returned.uid],original)
            positions.add(next(j for j,x in enumerate(s.pile) if x.uid==returned.uid))
            s.assert_instances()
        self.assertEqual(positions,set(range(5)))

    def test_immediate_draw_does_not_reset_stage_or_grant_base_energy(self):
        b=fixture('穿甲',('掠影','轻羽','风刃'))
        b.players[0].energy=2;b.players[0].spent=4
        s=play(b)
        self.assertEqual((s.stage,s.energy,s.spent,len(s.hand)),(1,2,6,3))

    def test_discard_moves_exact_instances_without_playing_them(self):
        b=fixture('战术大师',('天岚','穿空','轻羽'))
        s=b.players[0];s.hand.extend([s.pile.pop(0),s.pile.pop(0)])
        discarded={x.uid for x in s.hand[1:]};s.energy=1
        s=play(b)
        self.assertEqual(s.energy,2)
        self.assertTrue(discarded<={x.uid for x in s.discard})
        self.assertFalse(s.removed)
        self.assertEqual(s.layers['wind'],0)
        self.assertEqual(s.played,1)

    def test_recovery_is_not_draw_and_preserves_first_record(self):
        b=fixture('不灭烈焰',('火花','护盾'))
        s=b.players[0];inst=s.pile.pop(0);s.discard.append(inst);s.seen.add(inst.uid)
        s=play(b)
        self.assertIn(inst,s.hand);self.assertIn(inst.uid,s.seen)
        self.assertNotIn(inst.uid,s.drawn)
        self.assertFalse(any(e['kind']=='draw' for e in b.log))

    def test_discount_binds_instance_and_expires_when_leaving_hand(self):
        b=fixture('追云',('轻羽','轻羽'))
        s=play(b)
        self.assertEqual([b.cost(s,x) for x in s.hand],[0,0])
        ids={x.uid for x in s.hand}
        b.move_hand(s,1,'topdeck')
        self.assertEqual(len(s.discounts),1)
        self.assertEqual(len(ids),2)

    def test_same_instance_replay_never_repeats_first_layers(self):
        b=fixture('轻羽')
        s=play(b);self.assertEqual(s.layers['wind'],2)
        x=s.discard.pop();s.hand.append(x);s=play(b)
        self.assertEqual(s.layers['wind'],2)
        self.assertEqual(s.attack,102)

    def test_optional_search_can_select_zero_without_moving_candidates(self):
        b=fixture('穿云',('轻羽','掠影'))
        b.chooser=lambda public,candidates,count,purpose: []
        original=list(b.players[0].pile);s=play(b)
        self.assertEqual(s.pile,original);self.assertFalse(s.hand)

    def test_mandatory_search_rejects_an_empty_choice_when_target_exists(self):
        b=fixture('命运检索',('轻羽','掠影'))
        b.chooser=lambda public,candidates,count,purpose: []
        with self.assertRaises(ValueError):play(b)

class ResourceTests(unittest.TestCase):
    def test_income_and_free_windows(self):
        self.assertEqual([base_income(r) for r in range(1,10)],[2,2,2,3,3,3,3,4,4])
        p=Player(0,'fire')
        for r in range(1,21):
            for name in ('火花','余火','狂暴','燎原'):
                c=CARDS[name]
                expected=0 if (r<=2 and c.rarity=='common') or (3<=r<=4 and c.rarity in ('common','rare')) else {'common':1,'rare':2,'epic':3,'legendary':4}[c.rarity]
                p.free_used=False;self.assertEqual(free_price(p,c,r),expected)
                p.free_used=True;self.assertGreater(free_price(p,c,r),0)

    def test_starter_purchase_rejected_even_if_forged_offer(self):
        p=Player(0,'fire');p.deck=[]
        for name in START_ONLY:self.assertEqual(price_and_replace(p,name,1),(None,None))

    def test_removing_initial_or_gift_cards_never_mints_pool_tokens(self):
        pool=Pool();pool.remove(None)
        self.assertFalse(pool.pending);self.assertEqual(len(pool.tokens),912)
        pool.begin();self.assertEqual(sum(map(len,pool.free.values())),912)

    def test_combat_choice_ignores_hidden_enemy_pile(self):
        from .policy import choose_play
        b=fixture('掠影',('穿甲','轻羽'))
        b.players[0].hand.extend(b.players[0].pile);b.players[0].pile=[]
        first=choose_play(b,0)
        b.players[1].pile.reverse();b.players[1].rng.seed(777)
        self.assertEqual(choose_play(b,0),first)

    def test_tactic_zero_branch_is_player_stage_scoped(self):
        b=fixture('战术')
        b.players[0].energy=0;s=play(b)
        self.assertEqual(s.energy,1)
        x=s.discard.pop();s.hand.append(x);s.energy=0;s=play(b)
        self.assertEqual(s.energy,0)
        self.assertEqual(s.pending['energy'],0)

    def test_tactic_stores_all_mana_and_counts_actual_spending(self):
        b=fixture('战术');b.players[0].energy=3;s=play(b)
        self.assertEqual((s.energy,s.spent,s.pending['energy']),(0,3,4))

    def test_tailwind_is_once_per_player_stage(self):
        b=fixture('顺风');b.players[0].counts['wind']=2
        b.players[0].energy=0;s=play(b);self.assertEqual(s.energy,1)
        x=s.discard.pop();s.hand.append(x);s=play(b);self.assertEqual(s.energy,1)
        self.assertEqual(s.layers['wind'],1)

    def test_fire_activation_gate_and_ash_reward_cap(self):
        b=fixture('余烬刻度');s=b.players[0];s.layers['fire']=6
        s=play(b);self.assertEqual(s.ember,0)
        s.active.update(('炽焰王冠','灰烬循环'));s.ember=5
        b.consume_ember(s,5)
        self.assertEqual((s.pending['draw'],s.pending['energy']),(3,3))
        self.assertEqual(s.spent_ember,5)

    def test_tide_gate_and_no_recording_on_empty_heal(self):
        b=fixture('洪潮');s=b.players[0];s.layers['water']=10
        s=play(b);self.assertEqual(s.tide,0)
        s.active.add('潮汐之心');s.hp=1000;b.heal(s,100)
        self.assertEqual(s.tide,0)
        s.hp=900;b.heal(s,100)
        self.assertEqual(s.tide,55)  # 洪潮 itself first grants its water layer.

    def test_deep_growth_recomputes_instead_of_double_adding(self):
        b=fixture('深渊');s=b.players[0];s.active.add('潮汐之心');s.spent_tide=150
        s=play(b);self.assertEqual(b.stats(0)[0],111)
        s.tide=50;b.consume_tide(s,50)
        self.assertEqual(b.stats(0)[0],113)
        b.consume_tide(s,0);self.assertEqual(b.stats(0)[0],113)

    def test_life_flood_grows_max_hp_without_recording_heal(self):
        b=fixture('生命洪流');s=b.players[0];s.active.add('潮汐之心');s.tide=50;s.hp=1000
        s=play(b);self.assertEqual((s.max_hp,s.hp,s.tide,s.spent_tide),(1050,1050,0,50))

    def test_delayed_heal_batches_keep_each_tide_rounding_event(self):
        b=fixture('潮声');s=b.players[0];s.active.add('潮汐之心');s.hp=500
        s=play(b)
        x=s.discard.pop();s.hand.append(x);s=play(b)
        self.assertEqual(s.pending['heal_batches'],[25,25])
        s.tide=0;b.end_stage();b.time=100;b.begin_stage()
        self.assertEqual(b.players[0].tide,4)  # ceil25*5% twice, not ceil50*5%

    def test_payment_is_not_damage_and_trickle_uses_actual_payment(self):
        b=fixture('血刃');s=b.players[0];s.hp=100;s.fx['trickle']=2;s.fx['lifeguard']=1
        s=play(b);self.assertEqual(s.hp,100);self.assertFalse(s.guard_used)
        s.hp=1;self.assertEqual(b.pay_life(s,Q(1,2)),0)

class ShieldAndDamageTests(unittest.TestCase):
    def test_ordinary_shield_decay_merged_once_and_structure_rounds_once(self):
        b=fixture('攻击强化');s=b.players[0];s.shield=101;s.fx['shield_structure']=1
        b.shield_gain(s,10);b.shield_gain(s,10);loss=b.flush_shields(s)
        self.assertEqual((loss,s.shield),(25,99))

    def test_temporary_shield_has_own_expiry_and_converts_only_remaining(self):
        b=fixture('岩潮壁垒');s=play(b);self.assertEqual(s.shield_total,180)
        b.take_shield(s,80);b.end_stage();b.time=100;b.begin_stage();s=b.players[0]
        self.assertEqual(s.shield,50);self.assertFalse(s.temporary)

    def test_consuming_shield_does_not_trigger_break_rewards(self):
        b=fixture('碎岳之心');s=b.players[0];s.shield=100;s.fx['return_once']=100
        s=play(b);self.assertEqual((s.shield,s.fx['direct'],s.fx['return_once']),(75,50,100))

    def test_same_step_shield_consumption_and_enemy_cut_share_proportionally(self):
        b=fixture('山岳之躯',opponent='腐骨');s=b.players[0]
        s.hp=500;s.shield=100
        b.card_step({i:p.hand[0].uid for i,p in enumerate(b.players)})
        s=b.players[0]
        # Own request100, enemy request20; actual own spend=100*100/120.
        self.assertEqual((s.shield,s.hp),(0,667))
        self.assertEqual(b.executed['山岳之躯'],1)
        self.assertEqual(b.executed['腐骨'],1)
        json.dumps(b.log)  # rational shield quantities have exact JSON encoding

    def test_fixed_reduction_precedes_fire_and_percentage_multipliers(self):
        b=fixture('攻击强化');s,e=b.players
        s.layers['fire']=100;e.fx['next_flat']=20
        b.fire([0]);self.assertEqual(e.hp,920)

    def test_active_burst_return_only_if_target_survives(self):
        b=fixture('万钧碎盾');s=b.players[0];s.active.add('不周山');s.layers['earth']=10
        s=play(b)
        self.assertEqual(s.shield,60)
        self.assertEqual(b.players[1].hp,956)  # (150*11*3%-20)*1.5, floor once.

    def test_reflection_damage_can_trigger_return_but_not_recursive_reflection(self):
        b=fixture('攻击强化');s,e=b.players;e.shield=10;e.fx['return_flat']=50
        e.active.add('不周山');e.layers['earth']=10
        b.wave([b.packet(0,100,'burst')],reaction=True)
        self.assertEqual(e.shield,50)
        self.assertEqual(s.hp,1000)

    def test_main_only_bonus_and_penetration_do_not_leak_to_subs(self):
        b=fixture('攻击强化');s,e=b.players;s.fx['bonus']=100;s.fx['main_def_pen']=100
        s.subs=[(0,Q(1),1,False)];e.hp=e.max_hp=10000
        b.fire([0]);damages=[x['amount'] for x in b.log if x['kind']=='damage']
        self.assertEqual(damages,[200,60])

    def test_fractional_penetration_rounds_shield_allocation_before_life(self):
        b=fixture('攻击强化');s,e=b.players
        e.defense=0;e.shield=200;s.attack=101;s.layers['wind']=1
        b.fire([0]);self.assertEqual((e.shield,e.hp),(101,998))

    def test_both_auto_bursts_read_one_snapshot_before_defense_is_zeroed(self):
        b=fixture('攻击强化')
        for s in b.players:
            s.active.add('不周山');s.layers['earth']=100;s.shield=100;s.hp=10
        b.auto_burst()
        self.assertEqual(b.players[0].hp,b.players[1].hp)
        self.assertLessEqual(b.players[0].hp,0)

    def test_main_only_poison_attack_does_not_leak_to_submissiles(self):
        b=fixture('攻击强化');s,e=b.players;s.fx['main_attack']=50;s.subs=[(0,Q(1),1,False)]
        b.fire([0]);self.assertEqual([x['amount'] for x in b.log if x['kind']=='damage'],[110,60])

    def test_shield_amplification_does_not_amplify_overflow_life(self):
        b=fixture('攻击强化');s,e=b.players;e.shield=30;e.defense=0;s.fx['melt_shield']=1
        b.fire([0]);self.assertEqual((e.shield,e.hp),(0,925))

    def test_armor_break_applies_after_each_hit_and_expires(self):
        b=fixture('攻击强化');s,e=b.players;s.fx['armor_break']=4;s.subs=[(0,Q(1),1,False)]
        b.fire([0]);self.assertEqual(b.stats(1)[1],32)
        self.assertEqual([x['amount'] for x in b.log if x['kind']=='damage'],[60,64])
        self.assertEqual(s.fx['armor_break'],0)

    def test_wind_eye_suppresses_but_does_not_cleanse_permanent_reduction(self):
        b=fixture('风眼');s=b.players[0];s.fx['permanent_def_down']=30
        s=play(b);self.assertEqual(b.stats(0)[1],40)
        b.end_stage();b.time=100;b.begin_stage()
        self.assertEqual(b.stats(0)[1],10)

    def test_guard_covers_full_action_value_only_and_cannot_reset(self):
        b=fixture('气旋护壁');s=play(b);s.hp=10
        b.wave([b.packet(1,100,'true')]);self.assertEqual(s.hp,1)
        b.wave([b.packet(1,100,'true')]);self.assertEqual(s.hp,1)
        b.time=1;b.wave([b.packet(1,100,'true')]);self.assertLessEqual(s.hp,0)
        self.assertTrue(s.guard_used)

    def test_simultaneous_missiles_both_fire_even_when_lethal(self):
        b=fixture('攻击强化');a,e=b.players;a.hp=e.hp=10
        b.fire([0,1]);self.assertTrue(all(s.hp<=0 for s in b.players))

    def test_cleanse_does_not_erase_new_same_step_debuff(self):
        b=fixture('风之躯',opponent='磐石');s=b.players[0]
        s.mods.append(Modifier('atk_down',Q(10),1,2))
        b.card_step({i:p.hand[0].uid for i,p in enumerate(b.players)})
        self.assertEqual(b.players[0].value('atk_down'),20)

    def test_immediate_card_damage_locks_enemy_defense_before_its_same_step_card(self):
        b=fixture('潮汐风暴',opponent='防御强化');s=b.players[0]
        s.active.add('潮汐之心');s.tide=100
        b.card_step({i:p.hand[0].uid for i,p in enumerate(b.players)})
        self.assertEqual(b.players[1].hp,890)  # 150 raw minus snapshot40, not new43

    def test_final_attribute_multipliers_are_dynamic_and_stack(self):
        b=fixture('恐惧');play(b);s=b.players[1]
        self.assertEqual(b.stats(1),(80,32))
        s.attack+=50;self.assertEqual(b.stats(1)[0],120)

    def test_mixed_forge_counts_unplayed_instances_and_caps_at_six(self):
        b=fixture('元素熔炉',('润泽','活水','垒石','开岩','轻羽','掠影','毒引'))
        b.players[0].specialization='fire';s=play(b)
        self.assertEqual(s.layers['fire'],6)
        self.assertFalse(s.seen & {x.uid for x in s.pile})

    def test_magic_core_uses_starting_element_count_and_only_next_stage(self):
        b=fixture('魔法阵核心',('火花','润泽','垒石','轻羽','毒引'))
        b.players[0].energy=2;s=play(b);self.assertEqual(s.energy,0)
        b.end_stage();b.time=100;b.begin_stage();s=b.players[0]
        self.assertEqual(s.energy,4)
        self.assertEqual(len(s.hand),5)  # five unplayed non-ability cards remain

    def test_eternal_shield_uses_actual_hp_loss_including_payment(self):
        b=fixture('永恒壁垒');s=play(b)
        b.pay_life(s,Q(1,10));b.flush_shields(s);self.assertEqual(s.shield,100)
        b.wave([b.packet(1,120,'true')]);self.assertEqual(s.shield,195)

class PoisonAndTimelineTests(unittest.TestCase):
    def test_poison_bypasses_shield_and_uses_half_defense(self):
        b=fixture('攻击强化');s,e=b.players;s.layers['poison']=5;e.poison=3;e.shield=100
        b.wave(b.poison_packets(0));self.assertEqual((e.hp,e.shield),(999,100))
        s.specialization='poison';e.hp=1000;b.wave(b.poison_packets(0));self.assertEqual(e.hp,990)

    def test_explosion_uses_preconsume_snapshot_and_no_erosion_bonus(self):
        b=fixture('万毒爆');s,e=b.players;s.specialization='poison';s.layers['poison']=4;e.poison=3
        s.active.update(('万毒之源','毒爆','蚀命'));s=play(b)
        # attack120, first layer makes5:144 raw. Plague reduces defense to35;
        # explosion locks that pre-consumption defense, then floors144-17.5.
        self.assertEqual(b.players[1].hp,874)
        self.assertEqual((b.players[1].poison,s.attack),(0,123))

    def test_regular_poison_repeat_is_not_recursive(self):
        b=fixture('攻击强化');s,e=b.players;s.layers['poison']=10;e.poison=10;s.fx['poison_repeat']=2
        packets=b.poison_packets(0);self.assertEqual(len(packets),3);self.assertEqual(s.fx['poison_repeat'],0)

    def test_existing_wind_eye_suppresses_poison_damage_but_not_layer_changes(self):
        b=fixture('万毒爆');s,e=b.players;s.layers['poison']=10;e.poison=10
        e.mods.append(Modifier('negative_guard',Q(1),1,2));play(b)
        self.assertEqual((b.players[1].hp,b.players[1].poison),(1000,0))

    def test_new_same_step_wind_eye_does_not_cancel_snapshot_planned_poison(self):
        b=fixture('万毒爆',opponent='风眼');s,e=b.players;s.layers['poison']=10;e.poison=10
        b.card_step({i:p.hand[0].uid for i,p in enumerate(b.players)})
        self.assertLess(b.players[1].hp,1000)

    def test_guard_and_last_poison_prevent_actual_decay_trigger(self):
        b=fixture('攻击强化');s,e=b.players;s.active.add('蚀骨');s.layers['poison']=5;e.poison=1;e.poison_due=0
        s.fx.update(poison_guards=1,fast_rot=1);b.decay()
        self.assertEqual((e.poison,s.fx['poison_guards'],s.fx['fast_rot']),(1,1,1))

    def test_slow_poison_preserves_elapsed_progress(self):
        b=fixture('缓释毒素');s,e=b.players;e.poison=5;e.poison_start=0;e.poison_due=20;b.time=10
        s=play(b);self.assertEqual(b.players[1].poison_due,25)

    def test_poison_needle_arrives_before_next_stage_poison_tick(self):
        b=fixture('毒针');s=play(b);self.assertEqual(b.players[1].poison,0)
        b.end_stage();b.time=100;b.begin_stage()
        self.assertEqual(b.players[1].poison,1)
        self.assertTrue(any(x['kind']=='damage' and x['damage_kind']=='poison' for x in b.log))

    def test_rewind_restores_once_without_rewinding_instances(self):
        b=fixture('时光倒流');s=play(b);snapshot=s.rewind
        s.hp=-5;s.poison=6;b.finish_transaction();s=b.players[0]
        self.assertEqual(s.hp,snapshot[3]);self.assertEqual(s.poison,0)
        self.assertTrue(s.revived);self.assertTrue(any(x.name=='时光倒流' for x in s.removed))
        s.hp=-1;b.finish_transaction();self.assertEqual(s.hp,-1)

    def test_replay_and_seat_symmetry(self):
        decks=(TARGETS['风痕']['entries'],TARGETS['蚀骨']['entries'])
        a=Battle(decks,('wind','poison'),31).run()
        b=Battle(decks,('wind','poison'),31).run()
        reverse=Battle(decks[::-1],('poison','wind'),31).run()
        self.assertEqual(a,b)
        self.assertEqual(a['hp'],reverse['hp'][::-1])
        self.assertEqual(a['time'],reverse['time'])

if __name__=='__main__':unittest.main()
