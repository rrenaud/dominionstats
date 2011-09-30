""" This serves as a nice interface to the game documents stored in the db.  

Any information that can be derived from just the game state itself, and 
doesn't depend on foreign information, such as about the particular 
players in the game or other games in the collection belongs here.
"""

import collections
import pprint
from primitive_util import ConvertibleDefaultDict
import card_info
import itertools

WIN, LOSS, TIE = range(3)

class PlayerDeckChange(object):
    " This represents a change to a players deck in response to a game event."
    CATEGORIES = ['buys', 'gains', 'returns', 'trashes']

    def __init__(self, name):
        self.name = name
        # should I change this to using a dictionary of counts 
        # rather than a list?  Right now all the consumers ignore order,
        # but there is a similiar function specialized for accum in the
        # game class that uses a frequency dict.
        for cat in self.CATEGORIES:
            setattr(self, cat, [])
        self.vp_tokens = 0

    def merge_changes(self, other_changes):
        assert self.name == other_changes.name
        for cat in self.CATEGORIES:
            getattr(self, cat).extend(getattr(other_changes, cat))
        self.vp_tokens += other_changes.vp_tokens

class Turn(object):
    def __init__(self, turn_dict, game, player, turn_no, poss_no):
        self.game = game
        self.player = player
        self.plays = turn_dict.get('plays', [])
        self.gains = turn_dict.get('gains', [])
        self.buys = turn_dict.get('buys', [])
        self.turn_no = turn_no
        self.poss_no = poss_no
        self.turn_dict = turn_dict

    def __repr__(self):
        encoded = dict(self.turn_dict)
        encoded['player'] = self.player.name()
        encoded['turn_no'] = self.turn_no
        encoded['poss_no'] = self.poss_no
        return pprint.pformat(encoded)

    def get_player(self):
        return self.player

    def player_accumulates(self):
        return self.buys + self.gains

    def get_turn_no(self):
        return self.turn_no

    def get_poss_no(self):
        return self.poss_no

    def turn_label(self, for_anchor=False, for_display=False):
        if 'outpost' in self.turn_dict:
            fmt = u'%(pname)s-%(show)soutpost-turn-%(turn_no)d'
        elif self.poss_no:
            fmt = u'%(pname)s-%(show)sposs-turn-%(turn_no)d-%(poss_no)d'
        else:
            fmt = u'%(pname)s-%(show)sturn-%(turn_no)d'
        show = u'show-' if for_anchor else ''

        if for_display:
            fmt = fmt.replace('-', ' ')

        ret = fmt % {
            u'pname': self.player.name(),
            u'turn_no': self.turn_no - int(not (for_anchor or for_display)),
            u'poss_no': self.poss_no,
            u'show': show}

        if for_anchor:
            ret = ret.replace(' ', '-')
        return ret

    def money(self):
        return self.turn_dict.get('money', 0)

    def deck_changes(self):
        ret = []
        my_change = PlayerDeckChange(self.player.name())
        ret.append(my_change)
        my_change.gains = self.gains
        my_change.buys = self.buys
        my_change.trashes = self.turn_dict.get('trashes', [])
        my_change.returns = self.turn_dict.get('returns', [])
        my_change.vp_tokens += self.turn_dict.get('vp_tokens', 0)

        opp_info = self.turn_dict.get('opp', {})
        for opp_name, info_dict in opp_info.iteritems():
            change = PlayerDeckChange(opp_name)
            change.gains.extend(info_dict.get('gains', []))
            change.trashes.extend(info_dict.get('trashes', []))
            change.returns.extend(info_dict.get('returns', []))
            ret.append(change)

        return ret

class PlayerDeck(object):
    def __init__(self, player_deck_dict, game):
        self.raw_player = player_deck_dict
        self.game = game
        self.player_name = player_deck_dict['name']
        self.win_points = player_deck_dict['win_points']
        self.points = player_deck_dict['points']
        self.deck = player_deck_dict['deck']
        self.turn_order = player_deck_dict['order']
        self.num_real_turns = 0

    def name(self):
        return self.player_name

    def Points(self):
        return self.points

    def ShortRenderLine(self):
        return '%s %d<br>' % (self.name(), self.Points())

    def WinPoints(self):
        return self.win_points

    def TurnOrder(self):
        return self.turn_order

    def Resigned(self):
        return self.raw_player['resigned']

    def Deck(self):
        return self.deck

    def set_num_turns(self, t):
        self.num_real_turns = t

    def num_turns(self):
        return self.num_real_turns

    @staticmethod
    def PlayerLink(player_name, anchor_text=None):
        if anchor_text is None:
            anchor_text = player_name
        return '<a href="/player?player=%s">%s</a>' % (player_name,
                                                       anchor_text)

    def GameResultColor(self, opp=None):
        # this should be implemented in turns of GameResult.WinLossTie()
        if self.WinPoints() > 1:
            return 'green'
        if (opp and opp.WinPoints() == self.WinPoints()) or (
            self.WinPoints() == 1.0):
            return '#555555'
        return 'red'


class Game(object):
    def __init__(self, game_dict):
        self.turns = []
        self.supply = game_dict['supply']
        # pprint.pprint(game_dict)

        self.player_decks = [PlayerDeck(pd, self) for pd in game_dict['decks']]
        self.id = game_dict.get('_id', '')

        for raw_pd, pd in zip(game_dict['decks'], self.player_decks):
            turn_ct = 0
            poss_ct = 0
            out_ct = 0
            for turn in raw_pd['turns']:
                if 'poss' in turn:
                    poss_ct += 1
                elif 'outpost' in turn:
                    out_ct = 1
                else:
                    turn_ct += 1
                    poss_ct, out_ct = 0, 0
                self.turns.append(Turn(turn, game_dict, pd, turn_ct, poss_ct))
            pd.set_num_turns(turn_ct)

        self.turns.sort(key=lambda x: (x.get_turn_no(),
                                       x.get_player().TurnOrder(),
                                       x.get_poss_no()))


    def get_player_deck(self, player_name):
        for p in self.player_decks:
            if p.name() == player_name:
                return p
        assert ValueError, "%s not in players" % player_name

    #TODO: this could be made into a property
    def get_turns(self):
        return self.turns

    def get_supply(self):
        return self.supply

    def get_player_decks(self, sort_by_turn_order=False):
        if sort_by_turn_order:
            return sorted(self.player_decks, key=PlayerDeck.TurnOrder)
        else:
            return self.player_decks

    def all_player_names(self):
        return [pd.name() for pd in self.player_decks]

    #TODO: Nonfunctional?
    def get_winning_score(self):
        return self.winning_score

    @staticmethod
    def get_date_from_id(game_id):
        yyyymmdd_date = game_id.split('-')[1]
        return yyyymmdd_date

    def date(self):
        from datetime import datetime

        return datetime.strptime(Game.get_date_from_id(self.id), "%Y%m%d")

    def get_id(self):
        return self.id

    def isotropic_url(self):
        yyyymmdd_date = Game.get_date_from_id(self.id)
        path = '%s/%s/%s.gz' % (yyyymmdd_date[:6], yyyymmdd_date[-2:], self.id)
        return 'http://dominion.isotropic.org/gamelog/%s' % path

    @staticmethod
    def get_councilroom_link_from_id(game_id):
        return '<a href="/game?game_id=%s">' % game_id

    def get_councilroom_open_link(self):
        return self.get_councilroom_link_from_id(self.id)

    def dubious_quality(self):
        num_players = len(set(pd.name() for pd in self.get_player_decks()))
        if num_players < len(self.get_player_decks()): return True

        total_accumed_by_players = self.cards_accumalated_per_player()
        for player_name, accumed_dict in total_accumed_by_players.iteritems():
            if sum(accumed_dict.itervalues()) < 5:
                return True

        return False

    def win_loss_tie(self, targ, other=None):
        targ_deck = self.get_player_deck(targ)

        if other is None:
            other_win_points = 2 if targ_deck.WinPoints() == 0 else 0
        else:
            other_win_points = self.get_player_deck(other).WinPoints()

        if targ_deck.WinPoints() > 1 and other_win_points < 1:
            return WIN
        if other_win_points > 1:
            return LOSS
        return TIE

    def total_cards_accumulated(self):
        ret = collections.defaultdict(int)
        for turn in self.get_turns():
            for accumed_card in turn.player_accumulates():
                ret[accumed_card] += 1
        return ret

    # TODO(rrenaud): Get rid of this, and use DeckChangesPerPlayer() instead?
    def cards_accumalated_per_player(self):
        if 'card_accum_cache' in self.__dict__:
            return self.card_accum_cache
        ret = dict((pd.name(), collections.defaultdict(int)) for
        pd in self.get_player_decks())
        for turn in self.get_turns():
            for accumed_card in turn.player_accumulates():
                ret[turn.get_player().name()][accumed_card] += 1
        self.card_accum_cache = ret
        return ret

    def deck_changes_per_player(self):
        changes = {}
        for pd in self.get_player_decks():
            changes[pd.name()] = PlayerDeckChange(pd.name())
        for turn in self.get_turns():
            for change in turn.deck_changes():
                changes[change.name].merge_changes(change)
        return changes.values()

    def any_resigned(self):
        return any(pd.Resigned() for pd in self.get_player_decks())

    def short_render_cell_with_perspective(self, target_player,
                                           opp_player=None):
        target_deck = self.get_player_deck(target_player)
        opp_deck = None
        if opp_player is not None:
            opp_deck = self.get_player_deck(opp_player)
        color = target_deck.GameResultColor(opp_deck)

        ret = '<td>'
        ret += self.get_councilroom_open_link()
        ret += '<font color=%s>' % color
        ret += target_deck.ShortRenderLine()
        for player_deck in self.get_player_decks():
            if player_deck != target_deck:
                ret += player_deck.ShortRenderLine()
        ret += '</font></a></td>'
        return ret

    def game_state_iterator(self):
        return GameState(self)

def score_deck(deck_comp):
    """ Given a dict of card, frequency, return the score. """
    ret = 0
    if 'Gardens' in deck_comp:
        ret += score_gardens(deck_comp)
    if 'Duke' in deck_comp:
        ret += score_duke(deck_comp)
    if 'Fairgrounds' in deck_comp:
        ret += score_fairgrounds(deck_comp)
    if 'Vineyard' in deck_comp:
        ret += score_vineyard(deck_comp)

    for card in deck_comp:
        ret += card_info.vp_per_card(card) * deck_comp[card]

    return ret

def score_gardens(deck_comp):
    deck_size = sum(deck_comp.itervalues())
    return deck_size / 10 * deck_comp['Gardens']

def score_duke(deck_comp):
    return deck_comp['Duke'] * deck_comp.get('Duchy', 0)

def score_fairgrounds(deck_comp):
    return 2 * len(deck_comp.keys()) / 5 * deck_comp['Fairgrounds']

def score_vineyard(deck_comp):
    return sum(deck_comp[card] if card_info.is_action(card) else 0
               for card in deck_comp) / 3 * deck_comp['Vineyard']

class GameState(object):
    def __init__(self, game):
        self.game = game
        self.turn_ordered_players = game.get_player_decks(
            sort_by_turn_order=True)
        self.supply = ConvertibleDefaultDict(value_type=int)
        num_players = len(game.get_player_decks())
        for card in itertools.chain(card_info.EVERY_SET_CARDS,
                                    game.get_supply()):
            self.supply[card] = card_info.num_copies_per_game(card,
                                                              num_players)

        self.player_decks = ConvertibleDefaultDict(
            value_type=lambda: ConvertibleDefaultDict(int))
        self.player_vp_tokens = collections.defaultdict(int)

        self.supply['Copper'] = self.supply['Copper'] - (
            len(self.turn_ordered_players) * 7)

        for player in self.turn_ordered_players:
            self.player_decks[player.name()]['Copper'] = 7
            self.player_decks[player.name()]['Estate'] = 3

        self.turn_ind = 0

    def get_deck_composition(self, player):
        return self.player_decks[player]

    def player_score(self, player_name):
        return (score_deck(self.player_decks[player_name]) +
                self.player_vp_tokens[player_name])

    def encode_game_state(self):
        scores = {}
        for name in self.player_decks:
            scores[name] = self.player_score(name)

        ret = {
            'supply': self.supply.to_primitive_object(),
            'player_decks': self.player_decks.to_primitive_object(),
            'scores': scores,
            'label': self.turn_label(),
            'display_label': self.turn_label(for_display=True),
            'player': self.cur_turn.player.name() if self.cur_turn else '',
            'money': self.cur_turn.money() if self.cur_turn else 0,
            'turn_no': self.cur_turn.turn_no if self.cur_turn else
              self.game.get_turns()[-1].turn_no + 1
            }
        return ret

    def _player_at_turn_ind(self, given_turn_ind):
        return self.game.get_turns()[given_turn_ind].get_player()

    def player_turn_order(self):
        ret = []
        l = len(self.turn_ordered_players)
        offset = self.turn_ind % l
        for i in range(l):
            ret.append(self.turn_ordered_players[(i + offset) % l].name())
        return ret

    def turn_index(self):
        return self.turn_ind

    def _take_turn(self, turn):
        def apply_diff(cards, name, supply_dir, deck_dir):
            for card in cards:
                self.supply[card] += supply_dir
                self.player_decks[name][card] += deck_dir

        for deck_change in turn.deck_changes():
            apply_diff(deck_change.buys + deck_change.gains,
                      deck_change.name, -1, 1)
            apply_diff(deck_change.trashes, deck_change.name, 0, -1)
            apply_diff(deck_change.returns, deck_change.name, 1, -1)
            self.player_vp_tokens[deck_change.name] += deck_change.vp_tokens

    def turn_label(self, for_anchor=False, for_display=False):
        if not self.cur_turn:
            return 'end-game'
        return self.cur_turn.turn_label(for_anchor, for_display)

    def __iter__(self):
        self.turn_ind = 0
        self.cur_turn = self.game.get_turns()[self.turn_ind]
        yield self  # this yield self crap is ugly, leads to bugs :(
        for turn_ind, turn in enumerate(self.game.get_turns()):
            self.turn_ind = turn_ind + 1
            if self.turn_ind < len(self.game.get_turns()):
                self.cur_turn = self.game.get_turns()[self.turn_ind]
            else:
                self.cur_turn = None
            self._take_turn(turn)
            yield self

            
