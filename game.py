import collections
import pprint
from primitive_util import ConvertibleDefaultDict
import card_info
import itertools

WIN, LOSS, TIE = range(3)

class PlayerDeckChange(object):
    CATEGORIES = ['buys', 'gains', 'returns', 'trashes']

    def __init__(self, name):
        self.name = name
        # should I change this to using a dictionary of counts 
        # rather than a list?  Right now all the consumers ignore order,
        # but there is a similiar function specialized for accum in the
        # game class that uses a frequency dict.
        for cat in self.CATEGORIES:
            setattr(self, cat, [])

    def MergeChanges(self, other_changes):
        assert self.name == other_changes.name
        for cat in self.CATEGORIES:
            getattr(self, cat).extend(getattr(other_changes, cat))

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
        encoded['player'] = self.player.Name()
        encoded['turn_no'] = self.turn_no
        encoded['poss_no'] = self.poss_no
        return pprint.pformat(encoded)

    def Player(self):
        return self.player

    def PlayerAccumulates(self):
        return self.buys + self.gains

    def TurnNo(self):
        return self.turn_no

    def PossNo(self):
        return self.poss_no

    def DeckChanges(self):
        ret = []
        my_change = PlayerDeckChange(self.player.Name())
        ret.append(my_change)
        my_change.gains = self.gains
        my_change.buys = self.buys
        my_change.trashes = self.turn_dict.get('trashes', [])
        my_change.returns = self.turn_dict.get('returns', [])

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

    def Name(self):
        return self.player_name

    def Points(self):
        return self.points

    def ShortRenderLine(self):
        return '%s %d<br>' % (self.Name(), self.Points())

    def WinPoints(self):
        return self.win_points

    def TurnOrder(self):
        return self.turn_order

    def Resigned(self):
        return self.raw_player['resigned']

    def Deck(self):
        return self.deck

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
        self.WinPoints() == 1):
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

        self.turns.sort(key=lambda x: (x.TurnNo(),
                                       x.Player().TurnOrder(),
                                       x.PossNo()))

    def GetPlayerDeck(self, player_name):
        for p in self.player_decks:
            if p.Name() == player_name:
                return p
        assert ValueError, "%s not in players" % player_name

    def Turns(self):
        return self.turns

    def Supply(self):
        return self.supply

    def PlayerDecks(self):
        return self.player_decks

    def AllPlayerNames(self):
        return [pd.Name() for pd in self.player_decks]

    def WinningScore(self):
        return self.winning_score

    @staticmethod
    def DateFromId(game_id):
        yyyymmdd_date = game_id.split('-')[1]
        return yyyymmdd_date

    def Date(self):
        from datetime import datetime

        return datetime.strptime(Game.DateFromId(self.id), "%Y%m%d")

    def Id(self):
        return self.id

    def IsotropicUrl(self):
        yyyymmdd_date = Game.DateFromId(self.id)
        return 'http://dominion.isotropic.org/gamelog/%s/%s/%s.gz' % (
        yyyymmdd_date[:6], yyyymmdd_date[-2:], self.id)

    @staticmethod
    def CouncilRoomOpenLinkFromId(game_id):
        return '<a href="/game?game_id=%s">' % game_id

    def CouncilRoomOpenLink(self):
        return self.CouncilRoomOpenLinkFromId(self.id)

    def DubiousQuality(self):
        num_players = len(set(pd.Name() for pd in self.PlayerDecks()))
        if num_players < len(self.PlayerDecks()): return True

        total_accumed_by_players = self.CardsAccumulatedPerPlayer()
        for player_name, accumed_dict in total_accumed_by_players.iteritems():
            if sum(accumed_dict.itervalues()) < 5:
                return True

        return False

    def WinLossTie(self, targ, other=None):
        targ_deck = self.GetPlayerDeck(targ)

        if other is None:
            other_win_points = 2 if targ_deck.WinPoints() == 0 else 0
        else:
            other_win_points = self.GetPlayerDeck(other).WinPoints()

        if targ_deck.WinPoints() > 1 and other_win_points < 1:
            return WIN
        if other_win_points > 1:
            return LOSS
        return TIE

    def TotalCardsAccumulated(self):
        ret = collections.defaultdict(int)
        for turn in self.Turns():
            for accumed_card in turn.PlayerAccumulates():
                ret[accumed_card] += 1
        return ret

    # TODO(rrenaud): Get rid of this, and use DeckChangesPerPlayer() instead?
    def CardsAccumulatedPerPlayer(self):
        if 'card_accum_cache' in self.__dict__:
            return self.card_accum_cache
        ret = dict((pd.Name(), collections.defaultdict(int)) for
        pd in self.PlayerDecks())
        for turn in self.Turns():
            for accumed_card in turn.PlayerAccumulates():
                ret[turn.Player().Name()][accumed_card] += 1
        self.card_accum_cache = ret
        return ret

    def DeckChangesPerPlayer(self):
        changes = {}
        for pd in self.PlayerDecks():
            changes[pd.Name()] = PlayerDeckChange(pd.Name())
        for turn in self.Turns():
            for change in turn.DeckChanges():
                changes[change.name].MergeChanges(change)
        return changes.values()

    def AnyResigned(self):
        return any(pd.Resigned() for pd in self.PlayerDecks())

    def ShortRenderCellWithPerspective(self, target_player, opp_player=None):
        target_deck = self.GetPlayerDeck(target_player)
        opp_deck = None
        if opp_player is not None:
            opp_deck = self.GetPlayerDeck(opp_player)
        color = target_deck.GameResultColor(opp_deck)

        ret = '<td>'
        ret += self.CouncilRoomOpenLink()
        ret += '<font color=%s>' % color
        ret += target_deck.ShortRenderLine()
        for player_deck in self.PlayerDecks():
            if player_deck != target_deck:
                ret += player_deck.ShortRenderLine()
        ret += '</font></a></td>'
        return ret

    def GameStateIterator(self):
        return GameState(self)


class GameState(object):
    def __init__(self, game):
        self.game = game
        self.turn_ordered_players = sorted(game.PlayerDecks(),
                                           key=PlayerDeck.TurnOrder)
        self.supply = ConvertibleDefaultDict(value_type=int)
        num_players = len(game.PlayerDecks())
        for card in itertools.chain(card_info.EVERY_SET_CARDS, game.Supply()):
            self.supply[card] = card_info.NumCopiesPerGame(card, num_players)

        self.player_decks = ConvertibleDefaultDict(
            value_type=lambda: ConvertibleDefaultDict(int))

        self.supply['Copper'] = self.supply['Copper'] - (
        len(self.turn_ordered_players) * 7)

        for player in self.turn_ordered_players:
            self.player_decks[player.Name()]['Copper'] = 7
            self.player_decks[player.Name()]['Estate'] = 3

    def GetDeckComposition(self, player):
        return self.player_decks[player]

    def EncodeGameState(self):
        return {'supply': self.supply.ToPrimitiveObject(),
                'player_decks': self.player_decks.ToPrimitiveObject()}

    def _TakeTurn(self, turn):
        def ApplyDiff(cards, name, supply_dir, deck_dir):
            for card in cards:
                self.supply[card] += supply_dir
                self.player_decks[name][card] += deck_dir

        for deck_change in turn.DeckChanges():
            ApplyDiff(deck_change.buys + deck_change.gains,
                      deck_change.name, -1, 1)
            ApplyDiff(deck_change.trashes, deck_change.name, 0, -1)
            ApplyDiff(deck_change.returns, deck_change.name, 1, -1)

    def __iter__(self):
        yield self
        for turn in self.game.Turns():
            self._TakeTurn(turn)
            yield self
            
        
