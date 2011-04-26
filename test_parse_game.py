#!/usr/bin/python
# -*- coding: utf-8 -*-
try:
    import unittest2 as unittest
except ImportError, e:
    import unittest
import parse_game
import pprint

DEF_NAME_LIST = ['p' + str(x) for x in range(15)]

class CaptureCardsTest(unittest.TestCase):
    def test_capture_cards(self):
        captured = parse_game.capture_cards(
            'player0 plays 3 <span class=card-treasure>Coppers</span>.')
        self.assertEquals(captured, ['Copper'] * 3)
        
        captured = parse_game.capture_cards(
            '... ... and plays the <span class=card-none>Throne Room</span> '
            'again.')
        self.assertEquals(captured, ['Throne Room'])

        captured = parse_game.capture_cards(
            '... player0 gains the '
            '<span class=card-reaction>Watchtower</span>.')
        self.assertEquals(captured, ['Watchtower'])

        captured = parse_game.capture_cards(
            '... player1 gains a <span class=card-treasure>Copper</span> '
            'and a <span class=card-curse>Curse</span>')
        self.assertEquals(captured, ['Copper', 'Curse'])

        captured = parse_game.capture_cards(
            'player1 plays a <span class=card-treasure>Platinum</span>, '
            '3 <span class=card-treasure>Golds</span>, and a '
            '<span class=card-treasure>Copper</span>.')
        self.assertEquals(captured, ['Platinum', 'Gold', 'Gold', 'Gold',
                                     'Copper'])

        captured = parse_game.capture_cards(
            'cards in supply: <span cardname="Black Market" '
            'class=card-none>Black Market</span>, '
            '<span cardname="Caravan" class=card-duration>Caravan</span>')
        self.assertEquals(captured, ['Black Market', 'Caravan'])

        captured = parse_game.capture_cards(
            'player0 plays a <span class=card-none>Coppersmith</span>.')
        self.assertEquals(captured, ['Coppersmith'])
        
        captured = parse_game.capture_cards(
            'player4 buys an <span class=card-none>Expand</span>')
        self.assertEquals(captured, ['Expand'])

    def test_bane(self):
        captured = parse_game.capture_cards(
            '<span cardname="Chapel" class=card-none>Chapel</span>, <span cardname="Moat" class=card-reaction>Moat</span><span class=bane-star>&diams;</span>,')
        self.assertEquals(captured, ['Chapel', 'Moat'])

class DeleteKeysTest(unittest.TestCase):
    def test_delete_keys_with_empty_vals(self):
        d1 = {'p6': {}}
        parse_game.delete_keys_with_empty_vals(d1)
        self.assertEquals(d1, {})

    def test_ultimately_empty_nested_dict(self):
        d2 = {'p1': {'opp': {}}}
        parse_game.delete_keys_with_empty_vals(d2)
        self.assertEquals(d2, {})

class PlayerTrackerTest(unittest.TestCase):
    def setUp(self):
        self.tracker = parse_game.PlayerTracker()

    def test_simple_tracking(self):
        self.assertEquals(0, self.tracker.get_active_player(
                'player0 plays 3 <span class=card-treasure>Coppers</span>.'))

        self.assertEquals(self.tracker.current_player(), 0)

        self.assertEquals(0, self.tracker.get_active_player(
                'player0 buys a <span class=card-treasure>Silver</span>.'))

    def test_complicated_tracking(self):
        line_output_list = [
            ('player1 plays a <span class=card-none>Throne Room</span>.', 1),
            ('... and plays a <span class=card-none>Bureaucrat</span>.,', 1),
            ('... ... gaining a <span class=card-treasure>Silver</span> and putting it on the deck.', 1),
            ('... ... player2 puts an <span class=card-victory>Estate</span> back on the deck.', 2),
            ('... and plays the <span class=card-none>Bureaucrat</span> again.', 1),
            ('... ... gaining a <span class=card-treasure>Silver</span> and putting it on the deck.', 1),
            ('... ... player2 reveals 4 <span class=card-treasure>Golds</span>.', 2)]
        for line, expected_output in line_output_list:
            self.assertEquals(self.tracker.get_active_player(line), 
                              expected_output, line)
        self.assertEquals(self.tracker.current_player(), 1)

class ParseTurnHeaderTest(unittest.TestCase):
    def test_normal_turn(self):
        parsed_turn_header = parse_game.parse_turn_header(
            "--- player0's turn 3 ---", DEF_NAME_LIST)
        self.assertEquals(parsed_turn_header['name'], 'p0')
        self.assertEquals(parsed_turn_header['turn_no'], 3)

    def test_possesion_turn(self):
        parsed_turn_header = parse_game.parse_turn_header(
            "--- player0's turn (possessed by player1) ---", DEF_NAME_LIST)
        self.assertEquals(parsed_turn_header['name'], 'p0')
        self.assertEquals(parsed_turn_header['pname'], 'p1')

    def test_outpost_turn(self):
        parsed_turn_header = parse_game.parse_turn_header(
            """--- player0's extra turn (from <span class=card-duration>Outpost</span>) ---""", DEF_NAME_LIST)
        self.assertEquals(parsed_turn_header['name'], 'p0')
        self.assertEquals(parsed_turn_header['outpost'], True)

    def test_header_with_leading_space(self):
        parsed_turn_header = parse_game.parse_turn_header(
            "   --- player0's turn 3 ---", DEF_NAME_LIST)
        self.assertEquals(parsed_turn_header['name'], 'p0')
        self.assertEquals(parsed_turn_header['turn_no'], 3)

class ParseTurnTest(unittest.TestCase):
    def test_parse_turn(self):
        turn_info = parse_game.parse_turn(
u"""--- player0's turn 3 ---
   player0 plays 3 <span class=card-treasure>Coppers</span>.
   player0 buys a <span class=card-treasure>Silver</span>.
""", DEF_NAME_LIST)
        self.assertEquals(turn_info['name'], 'p0')
        self.assertEquals(turn_info['plays'], ['Copper', 'Copper', 'Copper'])
        self.assertEquals(turn_info['buys'], ['Silver'])
        self.assertEquals(turn_info['money'], 3)

    def test_chapel_turn(self):
        turn_info = parse_game.parse_turn(
u"""--- player5's turn 4 ---
player5 plays a <span class=card-none>Chapel</span>.
... trashing 2 <span class=card-treasure>Coppers</span>.
(player5 reshuffles.)""", DEF_NAME_LIST)
        self.assertEquals(turn_info['plays'], ['Chapel'])
        self.assertEquals(turn_info['trashes'], ['Copper', 'Copper'])
        self.assertTrue('opp' not in turn_info)

    def test_bishop_turn(self):
        turn_info = parse_game.parse_turn(
u"""--- player2's turn 7 ---
player2 plays a <span class=card-none>Bishop</span>.
... getting +$1 and +1 ▼.
... player2 trashes a <span class=card-treasure>Copper</span>.
... player3 trashes a <span class=card-treasure>Copper</span>.
player2 plays 3 <span class=card-treasure>Coppers</span>.
player2 buys a <span class=card-treasure>Silver</span>.""", DEF_NAME_LIST)
        self.assertEquals(turn_info['plays'], ['Bishop', 'Copper', 
                                               'Copper', 'Copper'])
        self.assertEquals(turn_info['trashes'], ['Copper'])
        self.assertEquals(turn_info['vp_tokens'], 1)
        self.assertEquals(turn_info['money'], 4)

    def test_bishop_turn2(self):
        turn_info = parse_game.parse_turn(
u"""--- player3's turn 3 ---
 player3 plays a <span class=card-none>Bishop</span>.
 ... getting +$1 and +1 ▼.
 ... player3 trashes an <span class=card-victory>Estate</span> and gets +1 ▼.
 ... player6 trashes nothing.
 player3 plays 3 <span class=card-treasure>Coppers</span>.
 player3 buys a <span class=card-none>Throne Room</span>.""", DEF_NAME_LIST)
        self.assertEquals(turn_info['trashes'], ['Estate'])
        self.assertTrue('opp' not in turn_info)
        self.assertEquals(turn_info['vp_tokens'], 2)
        self.assertEquals(turn_info['money'], 4)

    def test_bishop_turn3(self):
        turn_info = parse_game.parse_turn(
u"""   --- player6's turn 4 ---
    player6 plays a <span class=card-none>Bishop</span>.
    ... getting +$1 and +1 ▼.
    ... player6 trashes an <span class=card-victory>Estate</span> and gets +1 ▼.
    ... player3 trashes a <span class=card-treasure>Copper</span>.""", 
DEF_NAME_LIST)
        self.assertEquals(turn_info['vp_tokens'], 2)
        self.assertEquals(turn_info['trashes'], ['Estate'])
        self.assertEquals(turn_info['opp']['p3']['trashes'], ['Copper'])
        self.assertEquals(turn_info['money'], 1)

    def test_mine_upgrade_turn(self):
        turn_info = parse_game.parse_turn(u"""--- player3's turn 12 ---
player3 plays a <span class=card-none>Mine</span>.
... trashing a <span class=card-treasure>Talisman</span> and gaining a <span class=card-treasure>Gold</span>.
player3 plays a <span class=card-treasure>Gold</span>, a <span class=card-treasure>Royal Seal</span>, and a <span class=card-treasure>Copper</span>.
player3 buys a <span class=card-treasure>Gold</span>.
""", DEF_NAME_LIST)
        self.assertEquals(turn_info['gains'], ['Gold'])
        self.assertEquals(turn_info['buys'], ['Gold'])
        self.assertEquals(turn_info['trashes'], ['Talisman'])
        self.assertEquals(turn_info['money'], 6)

    def test_ambassador_turn(self):
        turn_info = parse_game.parse_turn(
u"""        --- player8's turn 3 ---
player8 plays an <span class=card-none>Ambassador</span>.
... player8 reveals an <span class=card-victory>Estate</span>.
... returning 2 copies to the supply.
... player9 gains an <span class=card-victory>Estate</span>.
""", DEF_NAME_LIST)
        self.assertEquals(turn_info['name'], 'p8')
        self.assertEquals(turn_info['plays'], ['Ambassador'])
        self.assertEquals(turn_info['returns'], ['Estate', 'Estate'])
        self.assertEquals(turn_info['opp']['p9']['gains'],
                          ['Estate'])

    def test_ambassador_secret_chamber_response_turn(self):
        input_str = u"""   --- player0's turn 16 ---
   player0 plays an <span class=card-none>Ambassador</span>.
   ... player1 reveals a <span class=card-reaction>Secret Chamber</span>.
   ... ... drawing 2 cards.
   ... ... returning 2 cards to the deck.
   ... player0 reveals a <span class=card-treasure>Copper</span>.
   ... returning 2 copies to the supply.
   ... player1 gains a <span class=card-treasure>Copper</span>."""
        turn_info = parse_game.parse_turn(input_str, DEF_NAME_LIST)
        self.assertEquals(turn_info['name'], 'p0')
        self.assertEquals(turn_info['plays'], ['Ambassador'])
        self.assertEquals(turn_info['returns'], ['Copper', 'Copper'])
        self.assertEquals(turn_info['opp']['p1']['gains'], ['Copper'])

    def test_ambassador3(self):
        turn_info = parse_game.parse_turn(
"""   --- player0's turn 6 ---
   player0 plays an <span class=card-none>Ambassador</span>.
   ... player0 reveals a <span class=card-treasure>Copper</span>.
   ... returning it to the supply.
   ... player1 gains a <span class=card-treasure>Copper</span>.""", 
['f', 't'])
        self.assertEquals(turn_info['returns'], ['Copper'])
        self.assertEquals(turn_info['opp']['t']['gains'], ['Copper'])

    def test_ambassador4(self):
        turn_info = parse_game.parse_turn(
"""--- player0's turn 4 ---
player0 plays an <span class=card-none>Ambassador</span>.
... revealing 2 <span class=card-treasure>Coppers</span> and returning them to the supply.
... player1 gains a <span class=card-treasure>Copper</span>.
""", DEF_NAME_LIST)
        self.assertEquals(turn_info['returns'], ['Copper', 'Copper'])

    def test_ambassador5(self):
        turn_info = parse_game.parse_turn("""--- player3's turn 8 ---
player3 plays a <span class=card-none>Worker's Village</span>.
... drawing 1 card and getting +2 actions and +1 buy.
player3 plays an <span class=card-none>Ambassador</span>.
... revealing a <span class=card-treasure>Copper</span> and returning it to the supply.
... player0 gains a <span class=card-treasure>Copper</span>.
player3 plays an <span class=card-none>Ambassador</span>.
... revealing nothing and returning them to the supply.
... player0 gains a <span class=card-treasure>Copper</span>.
""", DEF_NAME_LIST)
        self.assertEquals(turn_info['returns'], ['Copper'])
        self.assertEquals(turn_info['opp']['p0']['gains'], 
                          ['Copper', 'Copper'])

    def test_ambassador6(self):
        turn_info = parse_game.parse_turn("""--- player0's turn 8 ---
 player0 plays a <span class=card-none>Scout</span>.
 ... player0 reveals a <span class=card-treasure>Silver</span>, 2 <span class=card-treasure>Coppers</span>, and a <span class=card-none>Spy</span>.
 ... putting nothing into the hand.
 ... putting 4 cards back on the deck.
 player0 plays an <span class=card-none>Ambassador</span>.
 ... revealing an <span class=card-victory>Estate</span> and returning it to the supply.
 ... player1 gains an <span class=card-victory>Estate</span>.
 """, ['foo', 'bar'])
        self.assertEquals(turn_info['opp']['bar']['gains'], ['Estate'])

    def test_ambassador_moat(self):
        turn_info = parse_game.parse_turn(u"""--- player0's turn 10 ---
player0 plays an <span class=card-none>Ambassador</span>.
... player1 reveals a <span class=card-reaction>Moat</span>.
... revealing 2 <span class=card-victory>Estates</span> and returning them to the supply.""", DEF_NAME_LIST)
        self.assertEquals(turn_info['returns'], ['Estate', 'Estate'])


    def test_swindler_watchtower(self):
        turn_info = parse_game.parse_turn(u"""--- player0's turn 8 ---</a> 
   player0 plays a <span class=card-none>Swindler</span>.
   ... player1 turns up a <span class=card-none>Steward</span> and trashes it.
   ... replacing player1's <span class=card-none>Steward</span> with a <span class=card-reaction>Watchtower</span>.
   ... ... revealing a <span class=card-reaction>Watchtower</span>.
   ... ... trashing the <span class=card-reaction>Watchtower</span>.""",
                                          DEF_NAME_LIST)
        self.assertEquals(turn_info['opp']['p1']['gains'], ['Watchtower'])
        self.assertEquals(turn_info['opp']['p1']['trashes'], 
                          ['Steward', 'Watchtower'])

    def test_trading_post_turn(self):
        turn_info = parse_game.parse_turn(
"""--- player1's turn 11 ---
player1 plays a <span class=card-none>Trading Post</span>.
      ... player1 trashes a <span class=card-treasure>Copper</span> and an <span class=card-victory>Estate</span>, gaining a <span class=card-treasure>Silver</span> in hand.
      player1 plays a <span class=card-treasure>Copper</span> and a <span class=card-treasure>Silver</span>.
      player1 buys a <span class=card-treasure>Silver</span>.
      (player1 reshuffles.)
      <span class=logonly>(player1 draws: 2 <span class=card-curse>Curses</span>, a <span class=card-treasure>Copper</span>, a <span class=card-none>Trading Post</span>, and a <span class=card-none>Laboratory</span>.)</span>""", 
DEF_NAME_LIST)
        self.assertEquals(turn_info['trashes'], ['Copper', 'Estate'])
        self.assertEquals(turn_info['money'], 3)

    def test_sea_hag_turn(self):
        turn_info = parse_game.parse_turn(
"""--- player0's turn 14 ---
    player0 plays a <span class=card-none>Sea Hag</span>.
    ... player1 discards a <span class=card-none>Courtyard</span> and gains a <span class=card-curse>Curse</span> on top of the deck.""", DEF_NAME_LIST)
        self.assertEquals(turn_info['opp']['p1']['gains'], ['Curse'])

    def test_sea_hag_turn2(self):
        turn_info = parse_game.parse_turn("""
  --- player0's turn 6 ---
    player0 plays a <span class=card-none>Sea Hag</span>.
    ... player1 discards nothing and gains a <span class=card-curse>Curse</span> on top of the deck.
    player0 plays a <span class=card-treasure>Copper</span> and a <span class=card-treasure>Quarry</span>.
    player0 buys a <span class=card-none>Cutpurse</span>.
""", DEF_NAME_LIST)
        self.assertEquals(turn_info['opp']['p1']['gains'], ['Curse'])
        self.assertEquals(turn_info['money'], 2)

    def test_pirate_ship_turn(self):
        turn_info = parse_game.parse_turn(
u"""--- player8's turn 7 ---
player8 plays a <span class=card-none>Pirate Ship</span>.
... attacking the other players.
... (player11 reshuffles.)
... player11 reveals a <span class=card-duration>Wharf</span> and a <span class=card
-treasure>Copper</span>.
... player8 trashes player11's <span class=card-treasure>Copper</span>.
... player8 gains a <span class=card-none>Pirate Ship</span> token.
player8 plays 2 <span class=card-treasure>Coppers</span>.
""", DEF_NAME_LIST)
        self.assertEquals(turn_info['name'], 'p8')
        self.assertTrue('gains' not in turn_info)
        self.assertEquals(turn_info['money'], 2)
        self.assertTrue('opp' in turn_info, turn_info)
        self.assertEquals(turn_info['opp']['p11']['trashes'], ['Copper'])
        self.assertTrue('trashes' not in turn_info)
        self.assertEquals(turn_info['ps_tokens'], 1)

    def test_bank_turn(self):
        turn_info = parse_game.parse_turn(u"""
--- player2's turn 10 ---
player2 plays a <span class=card-treasure>Silver</span>, 2 <span class=card-treasure>Coppers</span>, and a <span class=card-treasure>Gold</span>.
player2 plays a <span class=card-treasure>Bank</span>.
... which is worth +$5.
player2 buys a <span class=card-victory>Province</span>.
""", DEF_NAME_LIST)
        self.assertEquals(turn_info['money'], 12)

    def test_philospher_stone_turn(self):
        turn_info = parse_game.parse_turn(u"""
--- player4's turn 15 ---
player4 plays a <span class=card-none>Laboratory</span>.
... drawing 2 cards and getting +1 action.
player4 plays a <span class=card-none>Laboratory</span>.
... drawing 2 cards and getting +1 action.
player4 plays a <span class=card-none>University</span>.
... getting +2 actions.
... gaining a <span class=card-none>Laboratory</span>.
player4 plays an <span class=card-none>Herbalist</span>.
... getting +1 buy and +$1.
player4 plays a <span class=card-treasure>Silver</span>.
player4 plays a <span class=card-treasure>Copper</span>.
player4 plays a <span class=card-treasure>Copper</span>.
player4 plays a <span class=card-treasure>Copper</span>.
player4 plays a <span class=card-treasure>Philosopher's Stone</span>.
... which is worth +$4 (6 cards in deck, 17 cards in discard).
player4 buys a <span class=card-none>Laboratory</span>.
player4 buys a <span class=card-none>Minion</span>.
player4 returns a <span class=card-treasure>Philosopher's Stone</span> to the top of the deck.
""", DEF_NAME_LIST)
        self.assertEquals(turn_info['money'], 10)

    def test_gain_via_workshop_turn(self):
        turn_info = parse_game.parse_turn(u"""
--- player0's turn 4 ---
player0 plays a <span class=card-none>Workshop</span>.
... gaining a <span class=card-none>Bridge</span>.
player0 plays 2 <span class=card-treasure>Coppers</span>.
player0 buys a <span class=card-none>Pawn</span>.
(player0 reshuffles.)
""", DEF_NAME_LIST)
        self.assertEquals(turn_info['plays'], ['Workshop', 'Copper', 'Copper'])
        self.assertEquals(turn_info['gains'], ['Bridge'])
        self.assertEquals(turn_info['buys'], ['Pawn'])
        self.assertEquals(turn_info['money'], 2)

    def test_golem_chapel_moat_turn(self):
        turn_info = parse_game.parse_turn(u"""--- player0's turn 9 ---
   player0 plays a <span class=card-none>Golem</span>.
   ... revealing a <span class=card-none>Witch</span>, and a <span class=card-none>Chapel</span>.
   ... playing the <span class=card-none>Witch</span> first.
   ... ... drawing 2 cards.
   ... ... player1 reveals a <span class=card-reaction>Moat</span>.
   ... playing the <span class=card-none>Chapel</span> second.
   ... ... trashing an <span class=card-victory>Estate</span>.""", 
                                          DEF_NAME_LIST)
        self.assertEquals(turn_info['plays'], ['Golem', 'Witch', 'Chapel'])
        self.assertEquals(turn_info['trashes'], ['Estate'])

    def test_throneroom_throneroom_pirateship_chapel_turn(self):
        turn_info = parse_game.parse_turn(u"""--- player0's turn 20 ---
   player0 plays a <span class=card-none>Throne Room</span>.
   ... and plays a <span class=card-none>Throne Room</span>.
   ... ... and plays a <span class=card-none>Pirate Ship</span>.
   ... ... ... attacking the other players.
   ... ... ... player1 reveals a <span class=card-victory>Province</span> and an <span class=card-victory>Estate</span>.
   ... ... and plays the <span class=card-none>Pirate Ship</span> again.
   ... ... ... attacking the other players.
   ... ... ... player1 reveals a <span class=card-none>Pirate Ship</span> and a <span class=card-none>Chapel</span>.
   ... and plays the <span class=card-none>Throne Room</span> again.
   ... ... and plays a <span class=card-none>Chapel</span>.
   ... ... ... trashing a <span class=card-victory>Gardens</span>.
   ... ... and plays the <span class=card-none>Chapel</span> again.
   ... ... ... trashing nothing.""", DEF_NAME_LIST)
        self.assertEquals(turn_info['trashes'], ['Gardens'])

    def test_throne_room_beaurcrat_turn(self):
        turn_info = parse_game.parse_turn(u"""--- player1's turn 13 ---
player1 plays a <span class=card-none>Throne Room</span>.
... and plays a <span class=card-none>Bureaucrat</span>.
... ... gaining a <span class=card-treasure>Silver</span> and putting it on the deck.
... ... player2 puts an <span class=card-victory>Estate</span> back on the deck.
... and plays the <span class=card-none>Bureaucrat</span> again.
... ... gaining a <span class=card-treasure>Silver</span> and putting it on the deck.
... ... player2 reveals 4 <span class=card-treasure>Golds</span>.""", 
                                          DEF_NAME_LIST)
        self.assertEquals(turn_info['gains'], ['Silver', 'Silver'])
        self.assertTrue(not 'opp' in turn_info, turn_info)
        
    def test_witch_turn(self):
        turn_info = parse_game.parse_turn(u"""
--- player0's turn 5 ---
player0 plays a <span class=card-none>Witch</span>.
... drawing 2 cards.
... player1 gains a <span class=card-curse>Curse</span>.
player0 plays 2 <span class=card-treasure>Coppers</span>.
player0 buys a <span class=card-duration>Lighthouse</span>.
""", DEF_NAME_LIST)
        self.assertEquals(turn_info['plays'], ['Witch', 'Copper', 'Copper'])
        self.assertTrue('gains' not in turn_info)
        self.assertEquals(turn_info['opp']['p1']['gains'], ['Curse'])
        self.assertEquals(turn_info['money'], 2)

    def test_swindler_turn(self):
        turn_info = parse_game.parse_turn(u"""--- player1's turn 9 ---
   player1 plays a <span class=card-none>Swindler</span>.
   ... getting +$2.
   ... player2 turns up a <span class=card-treasure>Silver</span> and trashes it.
   ... replacing player2's <span class=card-treasure>Silver</span> with a <span class=card-none>Shanty Town</span>.
   ... player3 turns up a <span class=card-none>Shanty Town</span> and trashes it.
   ... replacing player3's <span class=card-none>Shanty Town</span> with a <span class=card-none>Shanty Town</span>.""", DEF_NAME_LIST)
        self.assertEquals(turn_info['opp']['p2']['gains'], ['Shanty Town'])
        self.assertEquals(turn_info['opp']['p2']['trashes'], ['Silver'])
        self.assertEquals(turn_info['opp']['p3']['gains'], ['Shanty Town'])
        self.assertEquals(turn_info['opp']['p3']['trashes'], ['Shanty Town'])

    def test_swindler_turn2(self):
        turn_info = parse_game.parse_turn(u"""--- player0's turn 10 ---
 player0 plays a <span class=card-none>Worker's Village</span>.
 ... drawing 1 card and getting +2 actions and +1 buy.
 player0 plays a <span class=card-none>Swindler</span>.
 ... getting +$2.
 ... player1 turns up a <span class=card-treasure>Copper</span> and trashes it.
 ... replacing player1's <span class=card-treasure>Copper</span> with a <span class=card-curse>Curse</span>.
 player0 plays a <span class=card-none>Swindler</span>.
 ... getting +$2.
 ... player1 turns up an <span class=card-victory>Estate</span> and trashes it.
 ... replacing player1's <span class=card-victory>Estate</span> with an <span class=card-victory>Estate</span>.
 player0 plays 2 <span class=card-treasure>Coppers</span>.
 player0 buys a <span class=card-treasure>Gold</span>.""", DEF_NAME_LIST)
        self.assertEquals(turn_info['opp']['p1']['trashes'], 
                          ['Copper', 'Estate'])
        self.assertEquals(turn_info['opp']['p1']['gains'],
                          ['Curse', 'Estate'])

    def test_watchtower_mountebank_turn(self):
        turn_info = parse_game.parse_turn(u"""--- player0's turn 18 ---
    player0 plays a <span class=card-none>Throne Room</span>.
    ... and plays a <span class=card-none>Mountebank</span>.
    ... ... getting +$2.
    ... ... player1 gains a <span class=card-curse>Curse</span> and a <span class=card-treasure>Copper</span>.
    ... ... ... revealing a <span class=card-reaction>Watchtower</span> and trashing the <span class=card-curse>Curse</span>.
    ... ... ... revealing a <span class=card-reaction>Watchtower</span> and trashing the <span class=card-treasure>Copper</span>.""", DEF_NAME_LIST)
        self.assertEquals(turn_info['opp']['p1']['trashes'],
                          ['Curse', 'Copper'], turn_info)

    def test_watchtower_buy_curse_turn(self):
        turn_info = parse_game.parse_turn(u"""--- player0's turn 11 ---
   player0 buys a <span class=card-curse>Curse</span>.
   ... revealing a <span class=card-reaction>Watchtower</span> and trashing the <span class=card-curse>Curse</span>.""", DEF_NAME_LIST)
        self.assertEquals(turn_info['buys'], ['Curse'])
        self.assertEquals(turn_info['trashes'], ['Curse'])

    def test_thief_turn(self):
        turn_info = parse_game.parse_turn(u"""--- player0's turn 10 ---
 player0 plays a <span class=card-none>Thief</span>.
 ... player1 reveals a <span class=card-treasure>Silver</span> and an <span class=card-victory>Estate</span>.
 ... player0 trashes one of player1's <span class=card-treasure>Silvers</span>.
 ... player0 gains the trashed <span class=card-treasure>Silver</span>.""",
                                          DEF_NAME_LIST)
        self.assertEquals(turn_info['opp']['p1']['trashes'], ['Silver'])
        self.assertEquals(turn_info['gains'], ['Silver'])

    def test_mint_turn(self):
        turn_info = parse_game.parse_turn(u"""--- player0's turn 16 ---
    player0 plays a <span class=card-none>Mint</span>.
    ... revealing a <span class=card-treasure>Platinum</span> and gaining another one.""", DEF_NAME_LIST)
        self.assertEquals(turn_info['gains'], ['Platinum'])

    def test_explorer_turn(self):
        turn_info = parse_game.parse_turn(u"""--- player1's turn 19 ---
      player1 plays an <span class=card-none>Explorer</span>.
      ... revealing a <span class=card-victory>Province</span> and gaining a <span class=card-treasure>Gold</span> in hand.""", DEF_NAME_LIST)
        self.assertEquals(turn_info['gains'], ['Gold'])

    def test_saboteur_turn(self):
        turn_info = parse_game.parse_turn(u"""--- player2's turn 7 ---
player2 plays an <span class=card-none>Ironworks</span>.
... gaining an <span class=card-victory-action>Island</span>.
... (player2 reshuffles.)
... drawing 1 card and getting +1 action.
player2 plays a <span class=card-none>Saboteur</span>.
... player3 reveals an <span class=card-victory>Estate</span> and a <span class=card-treasure>Copper</span> and then a <span class=card-none>Baron</span>.
... The <span class=card-none>Baron</span> is trashed.
... player3 gains nothing to replace it.
... player9 reveals a <span class=card-none>Baron</span> and trashes it.
... player9 gains nothing to replace it.""", DEF_NAME_LIST)
        self.assertEquals(turn_info['opp']['p3']['trashes'], ['Baron'])
        self.assertEquals(turn_info['opp']['p9']['trashes'], ['Baron'])

    def test_saboteur_turn2(self):
        turn_info = parse_game.parse_turn("""--- player9's turn 14 ---
      player9 plays a <span class=card-none>Saboteur</span>.
      ... player2 reveals a <span class=card-none>Saboteur</span> and trashes it.
      ... player2 gains a <span class=card-treasure>Silver</span> to replace it.
      ... player3 reveals 3 <span class=card-treasure>Coppers</span> and then an <span class=card-victory-action>Island</span>.
      ... The <span class=card-victory-action>Island</span> is trashed.
      ... player3 gains nothing to replace it.
      player9 plays a <span class=card-treasure>Silver</span> and 3 <span class=card-treasure>Coppers</span>.
      player9 buys a <span class=card-none>Saboteur</span>.""", DEF_NAME_LIST)
        self.assertEquals(turn_info['opp']['p2']['trashes'], ['Saboteur'])
        self.assertEquals(turn_info['opp']['p2']['gains'], ['Silver'])
        self.assertEquals(turn_info['opp']['p3']['trashes'], ['Island'])

    def test_lookout_turn(self):
        turn_info = parse_game.parse_turn("""--- player2's turn 9 ---
           player2 plays a <span class=card-none>Lookout</span>.
   ... getting +1 action.
   ... (player2 reshuffles.)
   ... drawing 3 cards.
   ... trashing a <span class=card-treasure>Copper</span>.
   ... discarding a <span class=card-treasure>Copper</span>.
   ... putting a card back on the deck.""", DEF_NAME_LIST)
        self.assertEquals(turn_info['trashes'], ['Copper'])

    def test_coppersmith(self):
        turn_info = parse_game.parse_turn(u"""--- player0's turn 3 ---
player0 plays a <span class=card-none>Coppersmith</span>.
... making each <span class=card-treasure>Copper</span> worth $2.
player0 plays a <span class=card-treasure>Silver</span> and 2 <span class=card-treasure>Coppers</span>.
player0 buys a <span class=card-victory-action>Nobles</span>.
""", DEF_NAME_LIST)
        self.assertEquals(turn_info['name'], 'p0')
        self.assertEquals(turn_info['plays'],
                          ['Coppersmith', 'Silver', 'Copper', 'Copper'])
        self.assertEquals(turn_info['money'], 6)

    def test_UTF8_name(self):
        turn_info = parse_game.parse_turn(u"""--- player1's turn 1 ---
player1 plays 3 <span class=card-treasure>Coppers</span>.
player1 buys a <span class=card-none>Workshop</span>.
""", ['', u'Görling'])
        self.assertEquals(turn_info['name'], u'Görling')
        self.assertEquals(turn_info['money'], 3)

    def test_possessed_turn(self):
        turn_info = parse_game.parse_turn(
            u"""--- player0's turn (possessed by player1) ---
player0 plays a <span class=card-none>University</span>.
... gaining a <span class=card-none>Mint</span>.
... ... player1 gains the <span class=card-none>Mint</span>.
player0 plays a <span class=card-none>University</span>.
... gaining a <span class=card-none>Bazaar</span>.
... ... player1 gains the <span class=card-none>Bazaar</span>.""", 
            DEF_NAME_LIST)
        self.assertEquals(turn_info['name'], 'p1')
        self.assertEquals(turn_info['gains'], ['Mint', 'Bazaar'])
        self.assertTrue(turn_info['poss'])
        self.assertFalse('opp' in turn_info)

    def test_possessed_turn2(self):
        turn_info = parse_game.parse_turn(
            u"""--- player0's turn (possessed by player1) ---
 player0 plays a <span class=card-none>Remodel</span>.
 ... trashing a <span class=card-none>Mountebank</span>.
 ... gaining a <span class=card-treasure>Gold</span>.
 ... ... player1 gains the <span class=card-treasure>Gold</span>.
 player0 plays 2 <span class=card-treasure>Silvers</span>.
 player0 buys a <span class=card-none>Remodel</span>.
 ... player1 gains the <span class=card-none>Remodel</span>.
 (player0 reshuffles.)
 player0 discards the "trashed" card (a <span class=card-none>Mountebank</span>).""", DEF_NAME_LIST)
        self.assertEquals(turn_info['name'], 'p1')
        self.assertEquals(turn_info['gains'], ['Gold', 'Remodel'])
        self.assertFalse('buys' in turn_info)

    def test_possession_ambassador(self):
        turn_info = parse_game.parse_turn(u"""
--- player0's turn (possessed by player1) ---</a> 
    player0 plays an <span class=card-none>Ambassador</span>.
    ... revealing 2 <span class=card-victory>Duchies</span> and returning them to the supply.
    ... player1 gains a <span class=card-victory>Duchy</span>.
    player0 plays a <span class=card-treasure>Silver</span>.
    player0 buys an <span class=card-victory>Estate</span>.
    ... player1 gains the <span class=card-victory>Estate</span>.""",
                                          DEF_NAME_LIST)
        self.assertEquals(turn_info['gains'], ['Duchy', 'Estate'])
        self.assertEquals(turn_info['opp']['p0']['returns'], [
                'Duchy', 'Duchy'])

class CanonicalizeNamesTest(unittest.TestCase):
    def test_canonicalize_names(self):
        replaced = parse_game.canonicalize_names(
"""--- Zor Prime's turn 1 ---
Zor Prime plays 3 <span class=card-treasure>Coppers</span>.""",
['Zor Prime'])
        self.assertEquals(replaced,
"""--- player0's turn 1 ---
player0 plays 3 <span class=card-treasure>Coppers</span>.""")

    def test_name_as_substring(self):
        replaced = parse_game.canonicalize_names(
"""--- contain ed's turn 9 ---
   contain ed plays a <span class=card-none>Swindler</span>.
   ... getting +$2.
   ... contain turns up a <span class=card-treasure>Silver</span> and trashes it.""", ['contain', 'contain ed'])
        self.assertEquals(replaced,
"""--- player1's turn 9 ---
   player1 plays a <span class=card-none>Swindler</span>.
   ... getting +$2.
   ... player0 turns up a <span class=card-treasure>Silver</span> and trashes it.""")

    def test_evil_short_name(self):
        replaced = parse_game.canonicalize_names(
"""   --- d's turn 2 ---
    d plays 3 <span class=card-treasure>Coppers</span>.
    d buys a <span class=card-none>Masquerade</span>.
    (d reshuffles.)""", ['d'])
        self.assertEquals(replaced,
"""   --- player0's turn 2 ---
    player0 plays 3 <span class=card-treasure>Coppers</span>.
    player0 buys a <span class=card-none>Masquerade</span>.
    (player0 reshuffles.)""")
                          
class SplitTurnsTest(unittest.TestCase):
    def test_split_simple(self):
        split_turns = parse_game.split_turns(
"""--- player1's turn 1 ---
Foo
--- player2's turn 2 ---
Bar""")
        self.assertEquals(len(split_turns), 2)
        self.assertEquals(split_turns[0], "--- player1's turn 1 ---\nFoo\n")
        self.assertEquals(split_turns[1], "--- player2's turn 2 ---\nBar\n")

    def test_possesion_split(self):
        split_turns = parse_game.split_turns(
"""--- player0's turn (possessed by player1) ---
player0 plays an <span class=card-duration>Outpost</span>.
--- player2's turn 2 ---
Bar
--- player3's turn 1 ---
Ick""")
        self.assertEquals(len(split_turns), 3)
        self.assertEquals(split_turns[0], 
 "--- player0's turn (possessed by player1) ---\n"
 "player0 plays an <span class=card-duration>Outpost</span>.\n")
        
    def test_outpost_split(self):
        split_turns = parse_game.split_turns(
"""--- player0's turn 1 ---
... foo
--- player0's extra turn (from <span class=card-duration>Outpost</span>) ---
bar""")
        self.assertEquals(len(split_turns), 2)

    def test_curious_split(self):
        split_turns = parse_game.split_turns(
u"""--- player3's turn 1 ---
player3 plays 3 <span class=card-treasure>Coppers</span>.
player3 buys a <span class=card-treasure>Silver</span>.
<span class=logonly>(player3 draws: an <span class=card-victory>Estate</span> and 4 <span class=card-treasure>Coppers</span>.)</span>

   --- player2's turn 1 ---
   player2 plays 5 <span class=card-treasure>Coppers</span>.
   player2 buys a <span class=card-none>Festival</span>.
    <span class=logonly>(player2 draws: 3 <span class=card-victory>Estates</span> and 2 <span class=card-treasure>Coppers</span>.)</span>

--- player3's turn 2 ---
player3 plays 4 <span class=card-treasure>Coppers</span>.
player3 buys a <span class=card-treasure>Silver</span>.
(player3 reshuffles.)""")
        self.assertEquals(len(split_turns), 3)

class ParseTurnsTest(unittest.TestCase):
    def test_simple_input(self):
        turns_info = parse_game.parse_turns(u"""--- player3's turn 1 ---
player3 plays 3 <span class=card-treasure>Coppers</span>.
player3 buys a <span class=card-treasure>Silver</span>.
<span class=logonly>(player3 draws: an <span class=card-victory>Estate</span> and 4 <span class=card-treasure>Coppers</span>.)</span>

   --- player2's turn 1 ---
   player2 plays 5 <span class=card-treasure>Coppers</span>.
   player2 buys a <span class=card-none>Festival</span>.
    <span class=logonly>(player2 draws: 3 <span class=card-victory>Estates</span> and 2 <span class=card-treasure>Coppers</span>.)</span>

--- player3's turn 2 ---
player3 plays 4 <span class=card-treasure>Coppers</span>.
player3 buys a <span class=card-treasure>Silver</span>.
(player3 reshuffles.)
""", DEF_NAME_LIST)
        turn1Z = turns_info[0]
        self.assertEquals(turn1Z['name'], 'p3')
        self.assertEquals(turn1Z['plays'], ['Copper'] * 3)
        self.assertEquals(turn1Z['buys'], ['Silver'])

        turn1A = turns_info[1]
        self.assertEquals(turn1A['name'], 'p2')
        self.assertEquals(turn1A['plays'], ['Copper'] * 5)
        self.assertEquals(turn1A['buys'], ['Festival'])

        turn2Z = turns_info[2]
        self.assertEquals(turn2Z['name'], 'p3')
        self.assertEquals(turn2Z['plays'], ['Copper'] * 4)
        self.assertEquals(turn2Z['buys'], ['Silver'])

    def test_possesion_output_turns(self):
        turns = parse_game.parse_turns(u"""--- player0's turn (possessed by player1) ---
player0 plays an <span class=card-duration>Outpost</span>.
player0 plays 3 <span class=card-treasure>Golds</span>.
player0 buys a <span class=card-treasure>Gold</span>.
... player1 gains the <span class=card-treasure>Gold</span>.
<span class=logonly>(player0 draws: a <span class=card-treasure>Gold</span>, a <span class=card-none>Village</span>, and an <span class=card-duration>Outpost</span>.)</span> 
 
--- player0's extra turn (from <span class=card-duration>Outpost</span>) ---
player0 plays a <span class=card-none>Village</span>.
... (player0 reshuffles.)
... drawing 1 card and getting +2 actions.
player0 plays an <span class=card-duration>Outpost</span>.
player0 plays 2 <span class=card-treasure>Golds</span>.
player0 buys a <span class=card-treasure>Gold</span>.
<span class=logonly>(player0 draws: 2 <span class=card-treasure>Golds</span> and a <span class=card-none>Chapel</span>.)</span> """, DEF_NAME_LIST)
        self.assertEquals(len(turns), 2)

        self.assertTrue('outpost' in turns[1])
        self.assertEqual(turns[1]['buys'], ['Gold'])

class ParseDeckTest(unittest.TestCase):
    def test_deck(self):
        parsed_deck = parse_game.parse_deck(u"""<b>Snead: 75 points</b> (7 <span class=card-victory>Colonies</span>, 2 <span class=card-victory-action>Islands</span>, and an <span class=card-victory>Estate</span>); 22 turns
       opening: <span class=card-victory-action>Island</span> / <span class=card-treasure>Silver</span>
       [15 cards] 2 <span class=card-victory-action>Islands</span>, 1 <span class=card-none>Chapel</span>, 1 <span class=card-duration>Tactician</span>, 1 <span class=card-treasure>Silver</span>, 2 <span class=card-treasure>Platinums</span>, 1 <span class=card-victory>Estate</span>, 7 <span class=card-victory>Colonies</span>""")
        self.assertEquals(parsed_deck['name'], 'Snead')
        self.assertEquals(parsed_deck['points'], 75)
        self.assertEquals(parsed_deck['vp_tokens'], 0)
        self.assertEquals(parsed_deck['deck'],
                          {'Island': 2,
                           'Chapel': 1,
                           'Tactician': 1,
                           'Silver': 1,
                           'Platinum': 2,
                           'Estate': 1,
                           'Colony': 7})

    def test_deck_with_resign(self):
        parsed_deck = parse_game.parse_deck(u"""<b>#1 kiwi</b>: resigned (1st); 13 turns
      opening: <span class=card-none>Shanty Town</span> / <span class=card-none>Baron</span> 
      [23 cards] 8 <span class=card-none>Shanty Towns</span>, 5 <span class=card-none>Rabbles</span>, 2 <span class=card-none>Expands</span>, 1 <span class=card-none>Market</span>, 6 <span class=card-treasure>Coppers</span>, 1 <span class=card-victory>Estate</span> """)
        self.assertEquals(parsed_deck['resigned'], True)

    def test_20101213_style_deck(self):
        parsed_deck = parse_game.parse_deck(u"""<b>#1 zorkkorz</b>: 43 points (4 <span class=card-victory>Provinces</span>, 3 <span class=card-victory>Duchies</span>, 2 <span class=card-victory>Dukes</span>, and 2 <span class=card-victory-treasure>Harems</span>); 21 turns
          opening: <span class=card-none>Upgrade</span> / <span class=card-duration>Lighthouse</span> 
          [25 cards] 2 <span class=card-victory>Dukes</span>, 2 <span class=card-victory-treasure>Harems</span>, 2 <span class=card-none>Upgrades</span>, 1 <span class=card-none>Expand</span>, 1 <span class=card-duration>Lighthouse</span>, 4 <span class=card-treasure>Silvers</span>, 6 <span class=card-treasure>Golds</span>, 3 <span class=card-victory>Duchies</span>, 4 <span class=card-victory>Provinces</span> """)
        self.assertEquals(parsed_deck['name'], 'zorkkorz')

    def test20101213_style_deck_with_paren_name(self):
        parsed_deck = parse_game.parse_deck(u"""<b>#1 Foo (Bar)</b>: 43 points (4 <span class=card-victory>Provinces</span>, 3 <span class=card-victory>Duchies</span>, 2 <span class=card-victory>Dukes</span>, and 2 <span class=card-victory-treasure>Harems</span>); 21 turns
          opening: <span class=card-none>Upgrade</span> / <span class=card-duration>Lighthouse</span> 
          [25 cards] 2 <span class=card-victory>Dukes</span>, 2 <span class=card-victory-treasure>Harems</span>, 2 <span class=card-none>Upgrades</span>, 1 <span class=card-none>Expand</span>, 1 <span class=card-duration>Lighthouse</span>, 4 <span class=card-treasure>Silvers</span>, 6 <span class=card-treasure>Golds</span>, 3 <span class=card-victory>Duchies</span>, 4 <span class=card-victory>Provinces</span> """)
        self.assertEquals(parsed_deck['name'], 'Foo (Bar)')

    def test_20101226_evil_fing_name(self):
        parsed_deck = parse_game.parse_deck(u"""<b>#1 20 points</b>: 43 points (4 <span class=card-victory>Provinces</span>, 3 <span class=card-victory>Duchies</span>, 2 <span class=card-victory>Dukes</span>, and 2 <span class=card-victory-treasure>Harems</span>); 21 turns
          opening: <span class=card-none>Upgrade</span> / <span class=card-duration>Lighthouse</span> 
          [25 cards] 2 <span class=card-victory>Dukes</span>, 2 <span class=card-victory-treasure>Harems</span>, 2 <span class=card-none>Upgrades</span>, 1 <span class=card-none>Expand</span>, 1 <span class=card-duration>Lighthouse</span>, 4 <span class=card-treasure>Silvers</span>, 6 <span class=card-treasure>Golds</span>, 3 <span class=card-victory>Duchies</span>, 4 <span class=card-victory>Provinces</span> """)
        self.assertEquals(parsed_deck['name'], '20 points')
        self.assertEquals(parsed_deck['points'], 43)


    def test_deck_with_VP(self):
        parsed_deck = parse_game.parse_deck(u"""<b>Jon: 19 points</b> (16 ▼ and a <span class=card-victory>Duchy</span>); 20 turns
     opening: <span class=card-none>Salvager</span> / <span class=card-none>Black Market</span>
     [7 cards] 2 <span class=card-none>Bishops</span>, 1 <span class=card-duration>Tactician</span>, 1 <span class=card-treasure>Silver</span>, 2 <span class=card-treasure>Golds</span>, 1 <span class=card-victory>Duchy</span>""")
        self.assertEquals(parsed_deck['vp_tokens'], 16)

    def test_deck_with_VP2(self):
        parsed_deck = parse_game.parse_deck(u"""<b>Chrome: 12 points</b> (a <span class=card-victory>Province</span> and 6 ▼); 13 turns
        opening: <span class=card-none>Ironworks</span> / <span class=card-none>Black Market</span>
        [25 cards] 5 <span class=card-duration>Merchant Ships</span>, 5 <span class=card-none>Universities</span>, 2 <span class=card-none>Apprentices</span>, 2 <span class=card-none>Warehouses</span>, 1 <span class=card-none>Bishop</span>, 1 <span class=card-none>Black Market</span>, 1 <span class=card-none>Explorer</span>, 1 <span class=card-none>Worker's Village</span>, 6 <span class=card-treasure>Coppers</span>, 1 <span class=card-victory>Province</span>""")
        self.assertEquals(parsed_deck['vp_tokens'], 6)

    def test_parse_old_deck_with_paren(self):
        parsed_deck = parse_game.parse_deck(u"""<b>Jeremy (player1): 66 points</b> (8 <span class=card-victory>Provinces</span>, 4 <span class=card-victory>Duchies</span>, and 6 <span class=card-victory>Estates</span>); 28 turns
                     opening: <span class=card-none>Smithy</span> / <span class=card-treasure>Silver</span> 
                     [38 cards] 2 <span class=card-none>Smithies</span>, 7 <span class=card-treasure>Coppers</span>, 5 <span class=card-treasure>Silvers</span>, 6 <span class=card-treasure>Golds</span>, 6 <span class=card-victory>Estates</span>, 4 <span class=card-victory>Duchies</span>, 8 <span class=card-victory>Provinces</span> """)
        self.assertEquals(parsed_deck['name'], 'Jeremy (player1)')

    def test_deck_with_VP3(self):
        parsed_deck = parse_game.parse_deck(u"""<b>Chrome: 12 points</b> (a <span class=card-victory>Province</span> and 26 ▼); 13 turns
        opening: <span class=card-none>Ironworks</span> / <span class=card-none>Black Market</span>
        [25 cards] 5 <span class=card-duration>Merchant Ships</span>, 5 <span class=card-none>Universities</span>, 2 <span class=card-none>Apprentices</span>, 2 <span class=card-none>Warehouses</span>, 1 <span class=card-none>Bishop</span>, 1 <span class=card-none>Black Market</span>, 1 <span class=card-none>Explorer</span>, 1 <span class=card-none>Worker's Village</span>, 6 <span class=card-treasure>Coppers</span>, 1 <span class=card-victory>Province</span>""")
        self.assertEquals(parsed_deck['vp_tokens'], 26)

    def test_parse_empty_deck(self):
        # it's random BS like this that makes writing a dominion log parser
        # a pain.
        parsed_deck = parse_game.parse_deck(u"""<b>torchrat: 0 points</b> (nothing); 24 turns
          opening: <span class=card-none>Moneylender</span> / <span class=card-treasure>Silver</span>
          [0 cards] """)
        self.assertEquals(parsed_deck['vp_tokens'], 0)
        self.assertEquals(parsed_deck['deck'], {})

class AssignWinPointsTest(unittest.TestCase):
    def test_assign_win_points_simple(self):
        g = {'decks': [
                {'points': 2, 'turns': [None, None]},
                {'points': 1, 'turns': [None, None]}
                ]}
        parse_game.assign_win_points(g)
        self.assertEquals(g['decks'][0]['win_points'], 2.0)
        self.assertEquals(g['decks'][1]['win_points'], 0.0)

    def test_assign_win_points_break_ties_by_turns(self):
        g = {'decks': [
                {'points': 2, 'turns': [None, None]},
                {'points': 2, 'turns': [None]}
                ]}
        parse_game.assign_win_points(g)
        self.assertEquals(g['decks'][0]['win_points'], 0.0)
        self.assertEquals(g['decks'][1]['win_points'], 2.0)        
        
    def test_tie(self):
        g = {'decks': [
                {'points': 2, 'turns': [None, None]},
                {'points': 2, 'turns': [None, None]}
                ]}
        parse_game.assign_win_points(g)        
        self.assertEquals(g['decks'][0]['win_points'], 1.0)
        self.assertEquals(g['decks'][1]['win_points'], 1.0)

    def test_partial_tie(self):
        g = {'decks': [
                {'points': 2, 'turns': [None, None]},
                {'points': 2, 'turns': [None, None]},
                {'points': 1, 'turns': [None, None]}
                ]}
        parse_game.assign_win_points(g)        
        self.assertEquals(g['decks'][0]['win_points'], 1.5)
        self.assertEquals(g['decks'][1]['win_points'], 1.5)

class ParseGameHeaderTest(unittest.TestCase):
    def test_parse_header(self):
        parsed_header = parse_game.parse_header(u"""<html><head><link rel="stylesheet" href="/dom/client.css"><title>Dominion Game #2051</title></head><body><pre>AndMyAxe! wins!
All <span class=card-victory>Provinces</span> are gone.

cards in supply: <span cardname="Black Market" class=card-none>Black Market</span>, <span cardname="Caravan" class=card-duration>Caravan</span>, <span cardname="Chancellor" class=card-none>Chancellor</span>, <span cardname="City" class=card-none>City</span>, <span cardname="Council Room" class=card-none>Council Room</span>, <span cardname="Counting House" class=card-none>Counting House</span>, <span cardname="Explorer" class=card-none>Explorer</span>, <span cardname="Market" class=card-none>Market</span>, <span cardname="Mine" class=card-none>Mine</span>, and <span cardname="Pawn" class=card-none>Pawn</span>""")
        self.assertEquals(parsed_header['game_end'], ['Province'])
        self.assertEquals(parsed_header['supply'], ['Black Market',
                                                    "Caravan",
                                                    "Chancellor",
                                                    "City",
                                                    "Council Room",
                                                    "Counting House",
                                                    "Explorer",
                                                    "Market",
                                                    "Mine",
                                                    "Pawn"])

    def test_header_with_resign(self):
        parsed_header = parse_game.parse_header(u"""<html><head><link rel="stylesheet" href="/client.css"><title>Dominion Game #262</title></head><body><pre>uberme wins!
All but one player has resigned.
 
cards in supply: <span cardname="Bank" class=card-treasure>Bank</span>, <span cardname="Black Market" class=card-none>Black Market</span>, <span cardname="Colony" class=card-victory>Colony</span>, <span cardname="Hoard" class=card-treasure>Hoard</span>, <span cardname="Ironworks" class=card-none>Ironworks</span>, <span cardname="Militia" class=card-none>Militia</span>, <span cardname="Moneylender" class=card-none>Moneylender</span>, <span cardname="Platinum" class=card-treasure>Platinum</span>, <span cardname="Rabble" class=card-none>Rabble</span>, <span cardname="Scout" class=card-none>Scout</span>, <span cardname="Sea Hag" class=card-none>Sea Hag</span>, and <span cardname="Worker's Village" class=card-none>Worker's Village</span>
""")
        self.assertEquals(parsed_header['game_end'], [])
        self.assertEquals(parsed_header['resigned'], True)
        

    def test_parse_header_with_multi_end(self):
        parsed_header = parse_game.parse_header(u"""<html><head><link rel="stylesheet" href="/dom/client.css"><title>Dominion Game #3865</title></head><body><pre>stormybriggs wins!
<span class=card-victory>Duchies</span>, <span class=card-victory>Estates</span>, and <span class=card-none>Peddlers</span> are all gone.

cards in supply: <span cardname="Colony" class=card-victory>Colony</span>, <span cardname="Grand Market" class=card-none>Grand Market</span>, <span cardname="Loan" class=card-treasure>Loan</span>, <span cardname="Mine" class=card-none>Mine</span>, <span cardname="Monument" class=card-none>Monument</span>, <span cardname="Outpost" class=card-duration>Outpost</span>, <span cardname="Peddler" class=card-none>Peddler</span>, <span cardname="Platinum" class=card-treasure>Platinum</span>, <span cardname="Stash" class=card-treasure>Stash</span>, <span cardname="Warehouse" class=card-none>Warehouse</span>, <span cardname="Witch" class=card-none>Witch</span>, and <span cardname="Worker's Village" class=card-none>Worker's Village</span>
""")
        self.assertEquals(parsed_header['game_end'], ['Duchy', 'Estate', 
                                                      'Peddler'])
        self.assertEquals(parsed_header['resigned'], False)

class ValidateNamesTest(unittest.TestCase):
    def test_keyword_in_name(self):
        decks = [{'name': 'gains a curse'}]
        self.assertRaises(parse_game.BogusGameError, parse_game.validate_names,
                          decks)

    def test_starts_with_period(self):
        decks = [{'name': '.evil'}]
        self.assertRaises(parse_game.BogusGameError, parse_game.validate_names,
                          decks)

    def test_name_is_a(self):
        decks = [{'name': 'a'}]
        self.assertRaises(parse_game.BogusGameError, parse_game.validate_names,
                          decks)

class ParseGameTest(unittest.TestCase):
    def test_parse_game(self):
        parsed_game = parse_game.parse_game(u"""<html><head><link rel="stylesheet" href="/dom/client.css"><title>Dominion Game #2083</title></head><body><pre>Alenia wins!
All <span class=card-victory>Provinces</span> are gone.

cards in supply: <span cardname="Coppersmith" class=card-none>Coppersmith</span>, <span cardname="Expand" class=card-none>Expand</span>, <span cardname="Gardens" class=card-victory>Gardens</span>, <span cardname="Mining Village" class=card-none>Mining Village</span>, <span cardname="Nobles" class=card-victory-action>Nobles</span>, <span cardname="Outpost" class=card-duration>Outpost</span>, <span cardname="Pearl Diver" class=card-none>Pearl Diver</span>, <span cardname="Thief" class=card-none>Thief</span>, <span cardname="Throne Room" class=card-none>Throne Room</span>, and <span cardname="Worker's Village" class=card-none>Worker's Village</span>

----------------------

<b>Alenia: 58 points</b> (8 <span class=card-victory>Provinces</span> and 5 <span class=card-victory-action>Nobles</span>); 24 turns
        opening: <span class=card-treasure>Silver</span> / <span class=card-none>Coppersmith</span>
        [37 cards] 5 <span class=card-victory-action>Nobles</span>, 3 <span class=card-none>Expands</span>, 3 <span class=card-none>Pearl Divers</span>, 3 <span class=card-none>Worker's Villages</span>, 1 <span class=card-duration>Outpost</span>, 1 <span class=card-none>Throne Room</span>, 5 <span class=card-treasure>Coppers</span>, 8 <span class=card-treasure>Silvers</span>, 8 <span class=card-victory>Provinces</span>

<b>AndMyAxe!: 30 points</b> (5 <span class=card-victory>Gardens</span> [46 cards], 7 <span class=card-victory>Estates</span>, and a <span class=card-victory>Duchy</span>); 23 turns
           opening: <span class=card-treasure>Silver</span> / <span class=card-none>Worker's Village</span>
           [46 cards] 6 <span class=card-none>Worker's Villages</span>, 5 <span class=card-victory>Gardens</span>, 1 <span class=card-none>Coppersmith</span>, 1 <span class=card-duration>Outpost</span>, 1 <span class=card-none>Throne Room</span>, 21 <span class=card-treasure>Coppers</span>, 3 <span class=card-treasure>Silvers</span>, 7 <span class=card-victory>Estates</span>, 1 <span class=card-victory>Duchy</span>

----------------------

trash: a <span class=card-treasure>Silver</span>, 3 <span class=card-victory>Gardens</span>, a <span class=card-victory>Duchy</span>, 3 <span class=card-victory>Estates</span>, 2 <span class=card-treasure>Coppers</span>, a <span class=card-none>Coppersmith</span>, and 3 <span class=card-none>Expands</span>
league game: no

<hr/><b>Game log</b>

Turn order is Alenia and then AndMyAxe!.

<span class=logonly>(Alenia's first hand: 2 <span class=card-victory>Estates</span> and 3 <span class=card-treasure>Coppers</span>.)</span>
<span class=logonly>(AndMyAxe!'s first hand: 2 <span class=card-victory>Estates</span> and 3 <span class=card-treasure>Coppers</span>.)</span>

--- Alenia's turn 1 ---
Alenia plays 3 <span class=card-treasure>Coppers</span>.
Alenia buys a <span class=card-treasure>Silver</span>.
<span class=logonly>(Alenia draws: an <span class=card-victory>Estate</span> and 4 <span class=card-treasure>Coppers</span>.)</span>

   --- AndMyAxe!'s turn 1 ---
   AndMyAxe! plays 3 <span class=card-treasure>Coppers</span>.
   AndMyAxe! buys a <span class=card-treasure>Silver</span>.
   <span class=logonly>(AndMyAxe! draws: an <span class=card-victory>Estate</span> and 4 <span class=card-treasure>Coppers</span>.)</span>

--- Alenia's turn 2 ---
Alenia plays 4 <span class=card-treasure>Coppers</span>.
Alenia buys a <span class=card-none>Coppersmith</span>.
(Alenia reshuffles.)
<span class=logonly>(Alenia draws: an <span class=card-victory>Estate</span>, a <span class=card-treasure>Silver</span>, 2 <span class=card-treasure>Coppers</span>, and a <span class=card-none>Coppersmith</span>.)</span>

   --- AndMyAxe!'s turn 2 ---
   AndMyAxe! plays 4 <span class=card-treasure>Coppers</span>.
   AndMyAxe! buys a <span class=card-none>Worker's Village</span>.
   (AndMyAxe! reshuffles.)
   <span class=logonly>(AndMyAxe! draws: 2 <span class=card-victory>Estates</span> and 3 <span class=card-treasure>Coppers</span>.)</span>

--- Alenia's turn 3 ---
Alenia plays a <span class=card-none>Coppersmith</span>.
... making each <span class=card-treasure>Copper</span> worth $2.
Alenia plays a <span class=card-treasure>Silver</span> and 2 <span class=card-treasure>Coppers</span>.
Alenia buys a <span class=card-victory-action>Nobles</span>.
<span class=logonly>(Alenia draws: 2 <span class=card-victory>Estates</span> and 3 <span class=card-treasure>Coppers</span>.)</span>

All <span class=card-victory>Provinces</span> are gone.
Alenia wins!
</pre></body></html>""")
        self.assertEquals(parsed_game['players'], ['Alenia', 'AndMyAxe!'])
        self.assertEquals(parsed_game['decks'][0]['name'], 'Alenia')
        self.assertEquals(parsed_game['decks'][0]['points'], 58)
        self.assertEquals(parsed_game['decks'][0]['order'], 1)
        self.assertEquals(parsed_game['decks'][1]['name'], 'AndMyAxe!')
        self.assertEquals(parsed_game['decks'][1]['order'], 2)
        self.assertEquals(len(parsed_game['decks'][0]['turns']), 3)
        self.assertEquals(len(parsed_game['decks'][1]['turns']), 2)
        
        self.assertEquals(parsed_game['decks'][0]['win_points'], 2.0)
        self.assertEquals(parsed_game['decks'][1]['win_points'], 0.0)

        self.assertEquals(parsed_game['decks'][0]['turns'][2]['plays'], 
                          ['Coppersmith', 'Silver', 'Copper', 'Copper'])
        self.assertEquals(parsed_game['supply'],
                          ["Coppersmith", 
                           "Expand",
                           "Gardens",
                           "Mining Village",
                           "Nobles",
                           "Outpost",
                           "Pearl Diver",
                           "Thief", 
                           "Throne Room",
                           "Worker's Village"])

    EVIL_GAME_CONTENTS = u"""<html><head><link rel="stylesheet" href="/client.css"><title>Dominion Game #40068</title></head><body><pre>dcg wins!
All but one player has resigned.

cards in supply: <span cardname="Apprentice" class=card-none>Apprentice</span>, <span cardname="Familiar" class=card-none>Familiar</span>, <span cardname="Island" class=card-victory-action>Island</span>, <span cardname="Minion" class=card-none>Minion</span>, <span cardname="Possession" class=card-none>Possession</span>, <span cardname="Potion" class=card-treasure>Potion</span>, <span cardname="Royal Seal" class=card-treasure>Royal Seal</span>, <span cardname="Shanty Town" class=card-none>Shanty Town</span>, <span cardname="Throne Room" class=card-none>Throne Room</span>, <span cardname="Trade Route" class=card-none>Trade Route</span>, and <span cardname="Upgrade" class=card-none>Upgrade</span>

----------------------

<b>#1 dcg</b>: 3 points (3 <span class=card-victory>Estates</span>); 1 turns
     opening: <span class=card-treasure>Potion</span> / nothing
     [11 cards] 7 <span class=card-treasure>Coppers</span>, 1 <span class=card-treasure>Potion</span>, 3 <span class=card-victory>Estates</span>

<b>#2 8----------------------D</b>: resigned (1st); 2 turns
                          opening: <span class=card-none>Minion</span> / nothing
                          [11 cards] 1 <span class=card-none>Minion</span>, 7 <span class=card-treasure>Coppers</span>, 3 <span class=card-victory>Estates</span>

----------------------

trash: nothing
league game: no

<hr/><b>Game log</b>

Turn order is 8----------------------D and then dcg.

<span class=logonly>(8----------------------D's first hand: 5 <span class=card-treasure>Coppers</span>.)</span>
<span class=logonly>(dcg's first hand: an <span class=card-victory>Estate</span> and 4 <span class=card-treasure>Coppers</span>.)</span>

--- 8----------------------D's turn 1 ---
8----------------------D plays 5 <span class=card-treasure>Coppers</span>.
8----------------------D buys a <span class=card-none>Minion</span>.
<span class=logonly>(8----------------------D draws: 3 <span class=card-victory>Estates</span> and 2 <span class=card-treasure>Coppers</span>.)</span>

   --- dcg's turn 1 ---
   dcg plays 4 <span class=card-treasure>Coppers</span>.
   dcg buys a <span class=card-treasure>Potion</span>.
   <span class=logonly>(dcg draws: 2 <span class=card-victory>Estates</span> and 3 <span class=card-treasure>Coppers</span>.)</span>

--- 8----------------------D's turn 2 ---
8----------------------D resigns from the game (client disconnected).

All but one player has resigned.
dcg wins!
</pre></body></html>"""
    def test_parse_game_with_bogus_check(self):
        self.assertRaises(parse_game.BogusGameError, parse_game.parse_game,
                          ParseGameTest.EVIL_GAME_CONTENTS, True)

    def test_possesion_minigame(self):
        game_contents = u"""<html><head><link rel="stylesheet" href="/dom/client.css"><title>Dominion Game #888</title></head><body><pre>Leeko wins!
<span class=card-none>Bazaars</span>, <span class=card-none>Laboratories</span>, and <span class=card-curse>Curses</span> are all gone.
 
cards in supply: <span class=card-none>Bazaar</span>, <span class=card-none>Cutpurse</span>, <span class=card-none>Familiar</span>, <span class=card-victory>Gardens</span>, <span class=card-none>Laboratory</span>, <span class=card-none>Library</span>, <span class=card-none>Mint</span>, <span class=card-none>Possession</span>, <span class=card-treasure>Potion</span>, <span class=card-none>University</span>, and <span class=card-reaction>Watchtower</span> 

----------------------

<b>Leeko: 4 points</b> (a <span class=card-victory>Province</span>, 3 <span class=card-victory>Estates</span>, and 5 <span class=card-curse>Curses</span>); 17 turns
       opening: <span class=card-treasure>Silver</span> / <span class=card-treasure>Potion</span> 
       [40 cards] 9 <span class=card-none>Laboratories</span>, 7 <span class=card-none>Bazaars</span>, 5 <span class=card-none>Universities</span>, 2 <span class=card-none>Familiars</span>, 1 <span class=card-none>Cutpurse</span>, 1 <span class=card-none>Mint</span>, 1 <span class=card-reaction>Watchtower</span>, 2 <span class=card-treasure>Coppers</span>, 1 <span class=card-treasure>Silver</span>, 2 <span class=card-treasure>Potions</span>, 3 <span class=card-victory>Estates</span>, 1 <span class=card-victory>Province</span>, 5 <span class=card-curse>Curses</span> 

<b>michiel: 0 points</b> (3 <span class=card-victory>Estates</span> and 3 <span class=card-curse>Curses</span>); 16 turns
         opening: <span class=card-treasure>Potion</span> / <span class=card-reaction>Watchtower</span> 
         [28 cards] 3 <span class=card-none>Bazaars</span>, 3 <span class=card-none>Familiars</span>, 3 <span class=card-reaction>Watchtowers</span>, 2 <span class=card-none>Mints</span>, 1 <span class=card-none>Cutpurse</span>, 1 <span class=card-none>Laboratory</span>, 1 <span class=card-none>Possession</span>, 4 <span class=card-treasure>Coppers</span>, 1 <span class=card-treasure>Silver</span>, 2 <span class=card-treasure>Potions</span>, 1 <span class=card-treasure>Gold</span>, 3 <span class=card-victory>Estates</span>, 3 <span class=card-curse>Curses</span> 

----------------------
trash: 8 <span class=card-treasure>Coppers</span>, a <span class=card-treasure>Silver</span>, and 2 <span class=card-curse>Curses</span> 
league game: no
 
<hr/><b>Game log</b> 
 
Turn order is Leeko and then michiel.
<span class=logonly>(Leeko's first hand: 2 <span class=card-victory>Estates</span> and 3 <span class=card-treasure>Coppers</span>.)</span> 
<span class=logonly>(michiel's first hand: an <span class=card-victory>Estate</span> and 4 <span class=card-treasure>Coppers</span>.)</span> 
 
--- Leeko's turn 1 ---
Leeko plays 3 <span class=card-treasure>Coppers</span>.
Leeko buys a <span class=card-treasure>Silver</span>.
<span class=logonly>(Leeko draws: an <span class=card-victory>Estate</span> and 4 <span class=card-treasure>Coppers</span>.)</span> 
 
   --- michiel's turn 1 ---
   michiel plays 4 <span class=card-treasure>Coppers</span>.
   michiel buys a <span class=card-treasure>Potion</span>.
   <span class=logonly>(michiel draws: 2 <span class=card-victory>Estates</span> and 3 <span class=card-treasure>Coppers</span>.)</span> 

   --- michiel's turn 15 ---
   michiel plays a <span class=card-none>Laboratory</span>.
   ... drawing 2 cards and getting +1 action.
   michiel plays a <span class=card-none>Possession</span>.
   <span class=logonly>(michiel draws: a <span class=card-reaction>Watchtower</span>, a <span class=card-treasure>Potion</span>, a <span class=card-none>Familiar</span>, a <span class=card-treasure>Gold</span>, and a <span class=card-curse>Curse</span>.)</span> 

--- Leeko's turn (possessed by michiel) ---
Leeko plays a <span class=card-none>University</span>.
... gaining a <span class=card-none>Mint</span>.
... ... michiel gains the <span class=card-none>Mint</span>.
Leeko plays a <span class=card-none>University</span>.
... gaining a <span class=card-none>Bazaar</span>.
... ... michiel gains the <span class=card-none>Bazaar</span>.
Leeko plays 2 <span class=card-treasure>Coppers</span>.
(Leeko reshuffles.)
<span class=logonly>(Leeko draws: a <span class=card-none>University</span>, a <span class=card-none>Mint</span>, a <span class=card-none>Bazaar</span>, and 2 <span class=card-curse>Curses</span>.)</span>  

<span class=card-none>Bazaars</span>, <span class=card-none>Laboratories</span>, and <span class=card-curse>Curses</span> are all gone.
Leeko wins!
</pre></body></html> """
        parsed_game = parse_game.parse_game(game_contents)
        leeko_deck = parsed_game['decks'][0]
        self.assertEquals(leeko_deck['name'], 'Leeko')
        michiel_deck = parsed_game['decks'][1]
        self.assertEquals(michiel_deck['name'], 'michiel')
        self.assertEquals(len(leeko_deck['turns']), 1)
        self.assertEquals(len(michiel_deck['turns']), 3)
        self.assertTrue(michiel_deck['turns'][2]['poss'])
        # pprint.pprint(parsed_game)


if __name__ == '__main__':
    unittest.main()
