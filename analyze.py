 #!/usr/bin/python

""" Compute correlations between when/how many of a card is gained and wins."""

from __future__ import division

import os

import card_info
from stats import MeanVarStat
from game import Game
import incremental_scanner
import pymongo
import collections
import simplejson as json
from primitive_util import PrimitiveConversion, ConvertibleDefaultDict

import utils

class CardStatistic(PrimitiveConversion):
    """ Per card statistics.

        win_weighted_accum_turn:  Dictionary keyed by turn that correlates
            winning and gaining/buying the card on a given turn.  It is
            weighted in the sense that if a card is bought twice in a given
            turn, it counts twice for that turn.

        win_diff_accum:  Dictionary keyed by relative card advantage that
            correlates winning and have an advantage/disadvantage in the
            number of a given card.  Card advantages are rounded relative
            to the average number gained/bought by other players through the
            game.
    """
    def __init__(self):
        self.available = 0
        self.win_any_accum = MeanVarStat()
        self.win_weighted_accum = MeanVarStat()
        self.win_weighted_accum_turn = ConvertibleDefaultDict(MeanVarStat, int)
        self.win_diff_accum = ConvertibleDefaultDict(MeanVarStat, int)
        
class GamesAnalysis(PrimitiveConversion):
    """ A collection of CardStatistics for every card in the deck. """

    def __init__(self):
        self.card_stats = ConvertibleDefaultDict(CardStatistic)
        self.num_games = 0
        self.max_game_id = ''
        
    def analyze_game(self, game):
        """ Aggregate information about game into this object.

        game: game.Game object to analyze.
        """
        self.num_games += 1
        seen_cards_players = set()
        self.max_game_id = max(self.max_game_id, game.get_id())
        for card in game.get_supply() + card_info.EVERY_SET_CARDS:
            self.card_stats[card].available += len(game.get_player_decks())

        accumed_by_player = collections.defaultdict(lambda : collections.defaultdict(int))
        for turn in game.get_turns():
            deck = turn.get_player()
            turnno = turn.get_turn_no()
            for card in turn.player_accumulates():
                per_card_stat = self.card_stats[card]
                if (deck, card) not in seen_cards_players:
                    seen_cards_players.add((deck, card))
                    per_card_stat.win_any_accum.AddOutcome(deck.WinPoints())
                per_card_stat.win_weighted_accum.AddOutcome(deck.WinPoints())
                per_card_stat.win_weighted_accum_turn[turnno].AddOutcome(
                    deck.WinPoints())
                accumed_by_player[deck][card] += 1
                
        for deck, card_accum_dict in accumed_by_player.iteritems():
            total_other_decks = collections.defaultdict(int)
            odeck_count = 0
            for other_deck, other_accum in accumed_by_player.iteritems():
                if other_deck != deck:
                    odeck_count += 1
                    for card in other_accum:
                        total_other_decks[card] += other_accum[card]
            assert odeck_count != 0, game.isotropic_url()
            for card in set(card_accum_dict.keys() + total_other_decks.keys()):
                per_card_stat = self.card_stats[card]
                other_avg_freq = total_other_decks[card] / odeck_count
                card_diff_index = int(card_accum_dict[card] - other_avg_freq)
                per_card_stat.win_diff_accum[card_diff_index].AddOutcome(
                    deck.WinPoints())

def main():
    """ Update analysis statistics.  By default, do so incrementally, unless
    --noincremental argument is given."""
    parser = utils.incremental_max_parser()
    parser.add_argument('--output_collection_name', default='analysis')

    args = parser.parse_args()

    conn = pymongo.Connection()
    database = conn.test
    games = database.games

    output_collection_name = args.output_collection_name
    output_collection = database[output_collection_name]
    game_analysis = GamesAnalysis()

    scanner = incremental_scanner.IncrementalScanner(output_collection_name,
                                                     database)
 
    if args.incremental:
        utils.read_object_from_db(game_analysis, output_collection, '')
    else:
        scanner.reset()

    output_file_name = 'static/output/all_games_card_stats.js'

    if not os.path.exists('static/output'):
        os.makedirs('static/output')

    print scanner.status_msg()

    for idx, raw_game in enumerate(scanner.scan(games, {})):
        try:
            if idx % 1000 == 0:
                print idx
            game_analysis.analyze_game(Game(raw_game))

            if idx == args.max_games:
                break
        except int, exception:
            print Game(raw_game).isotropic_url()
            print exception
            print raw_game
            raise 

    game_analysis.max_game_id = scanner.get_max_game_id()
    game_analysis.num_games = scanner.get_num_games()
    utils.write_object_to_db(game_analysis, output_collection, '')

    output_file = open(output_file_name, 'w')
    output_file.write('var all_card_data = ')

    json.dump(game_analysis.to_primitive_object(), output_file)
    print scanner.status_msg()
    scanner.save()

if __name__ == '__main__':
    main() 
