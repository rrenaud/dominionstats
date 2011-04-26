import urllib

import pymongo

import card_info
import game
import name_merger

def _RenderCard(card, freq, kingdom_restrict):
    def FontSize(freq):
        if freq >= 10:
            return "+2"
        elif not freq:
            return "-1"
        else:
            return "+0"

    font_size = FontSize(freq)
    plural = card_info.Pluralize(card, freq)

    rendered = '<font size="%s">%d %s</font>' % (font_size, freq, plural)
    if card in kingdom_restrict:
        rendered = '<b>' + rendered + '</b>'
    return rendered
    

class _DeckMatcher(object):
    def __init__(self, player_deck, query_matcher):
        self.player_deck = player_deck
        self.query_matcher = query_matcher

        self.kingdom_match_score = 0
        if query_matcher.kingdom_restrict:
            kingdom_freqs = []
            for card in query_matcher.kingdom_restrict:
                kingdom_freqs.append(player_deck.Deck().get(card, 0))

            has_all = True
            kingdom_total_matched = 0
            for freq in kingdom_freqs:
                if not freq:
                    has_all = False
                kingdom_total_matched += freq
            # TODO: maybe make this score product like rather than sum like, so
            # it rewards having a balanced match.
            # This would also be improved by examining the game and seeing when
            # cards were played in case they are later trashed.
            self.kingdom_match_score = kingdom_total_matched * 10 + (
                has_all * 100)
        self.name_match_score = query_matcher.NameMatch(
            player_deck.Name()) * 10000

    def DeckMatchScore(self):
        return self.kingdom_match_score + self.name_match_score

    def KingdomMatchScore(self):
        return self.kingdom_match_score

    def _MaybeHighlightName(self, name):
        if self.query_matcher.NameMatch(name):
            return '<b>%s</b>' % name
        return name

    def DisplayPlayerDeck(self):
        pd = self.player_deck
        ret = ''
        ret += '%s: %d points: ' % (
            game.PlayerDeck.PlayerLink(
                pd.Name(),
                '<font color="%s">%s</font>' % (
                    self.player_deck.GameResultColor(),
                    self._MaybeHighlightName(pd.Name()))
                ),
            pd.Points())
        card_freqs = pd.Deck().items()
        card_freqs.sort(key = lambda card_freq: -card_freq[1])
        first = True
        for card, freq in card_freqs:
            if not first:
                ret += ', '
            first = False
            ret += _RenderCard(card, freq, self.query_matcher.kingdom_restrict)
        if self.query_matcher.debug_level > 0:
            ret += '<i><font size="-1"> name:%d kingdom:%d</font></i>' % (
                self.name_match_score, self.kingdom_match_score)
        ret += '<br>'
        return ret


class GameMatcher(object):
    def __init__(self, g, query_matcher):
        self.g = g
        self.query_matcher = query_matcher
        self.deck_matches = []
        for pd in g.PlayerDecks():
            self.deck_matches.append(_DeckMatcher(pd, query_matcher))
        self.deck_matches.sort(key=_DeckMatcher.DeckMatchScore, reverse=True)

        kingdom_match_scores = [dm.KingdomMatchScore() for dm in
                                self.deck_matches]
        self.kingdom_match_diff = max(kingdom_match_scores) - min(
            kingdom_match_scores)

        self.sum_deck_match_score = sum(
        dm.DeckMatchScore() for dm in self.deck_matches)
        # newness a tiebreaker, should always be less than 1
        self.newness = float(game.Game.DateFromId(self.g.Id())) / 1e9
        self.final_score = (self.sum_deck_match_score +
                            2 * self.kingdom_match_diff + self.newness)

    def _GameMatchScore(self):
        return self.final_score

    def _DisplaySupply(self):
        total_accum_dict = self.g.TotalCardsAccumulated()
        supply = sorted(self.g.Supply(),
                        key=lambda x: -total_accum_dict[x])
        rendered_supply_items = []
        for card in supply:
            freq = total_accum_dict[card]
            rendered_supply_items.append(
                _RenderCard(card, freq, self.query_matcher.kingdom_restrict))

        return ', '.join(rendered_supply_items)


    def DisplayGameSnippet(self):
        ret = '%s%s</a>' % (self.g.CouncilRoomOpenLink(),
                            self._DisplaySupply())
        if self.query_matcher.debug_level > 0:
            ret += (' <i><font size="-1">'
                    'final:%f kingdom diff:%f sum deck match :%f new:%f'
                    '</font></i>') % (
            self.final_score, self.kingdom_match_diff,
            self.sum_deck_match_score, self.newness)
        ret += '<br>'
        for deck_match in self.deck_matches:
            ret += deck_match.DisplayPlayerDeck()
        return ret


class QueryMatcher(object):
    def __init__(self, **args):
        self.exact_names = []
        self.players_restrict = []
        self.kingdom_restrict = []
        self.limit = 200
        self.debug_level = args.get('debug', 0)

        if 'p1_name' in args:
            self._AddName(args['p1_name'])
        if 'p2_name' in args:
            self._AddName(args['p2_name'])
        if 'kingdom' in args:
            def sane_title(card):
                return card.title().replace("'S", "'s")

            self.kingdom_restrict = [sane_title(k).strip()
                                     for k in args['kingdom'].split(',')]

        self.db_query = {}
        if self.players_restrict:
            self.db_query['players'] = {'$all': self.players_restrict}

        if self.kingdom_restrict:
            self.db_query['supply'] = {'$all': self.kingdom_restrict}

    def _AddName(self, name):
        if type(name) is not unicode:
            name = name.decode('utf8')
        self.players_restrict.append(name_merger.norm_name(name))
        self.exact_names.append(name)

    def NameMatch(self, name):
        return (name in self.exact_names) + (
        name_merger.norm_name(name) in self.players_restrict)

    def QueryDB(self, table):
        # TODO support sorting options:
        #   player skill
        results = []
        games_cursor = table.find(self.db_query)
        for raw_game in games_cursor.sort('_id', pymongo.DESCENDING
        ).limit(self.limit):
            results.append(GameMatcher(game.Game(raw_game), self))
        results.sort(key=GameMatcher._GameMatchScore, reverse=True)
        return results
