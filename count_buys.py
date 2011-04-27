#!/usr/bin/python

"""Computes stats about buys/gains and game length for all cards in the game.

When this is called as a stand alone program, it will will incrementally
update statistics for all games in the database.
"""

import time

import pymongo

from stats import MeanVarStat as MVS
import card_info
import game
import incremental_scanner
import mergeable
import primitive_util
import utils

NO_INFO = MVS().meanDiff(MVS())

class BuyStat(primitive_util.PrimitiveConversion, mergeable.MergeableObject):
    """ A bunch of MeanVar statistics about card buys/game length, etc """

    def __init__(self):
        self.buys = MVS()
        self.gains = MVS()
        self.trashes = MVS()
        self.returns = MVS()
        self.any_gained = MVS()
        self.available = MVS()
        self.game_length = MVS()
        self.game_length_colony = MVS()
    
    @property
    def none_gained(self):
        return self.available - self.any_gained

    def effect_with(self):
        return getattr(self, 'effectiveness_gain', NO_INFO)
    
    def effect_without(self):
        return getattr(self, 'effectiveness_skip', NO_INFO)

class DeckBuyStats(primitive_util.ConvertibleDefaultDict,
                   mergeable.MergeableDict):
    """ Essentially, a defaultdict of BuyStats.

    Since this is convertible, it can be easily turned into a value that
    consists of nothing but primitive types, which is nice for mongo and JSON.
    Likewise, it can be recreated from such a value.

    Since it is mergeable, it can be combined with another DeckBuysInstance to
    tell the combined story.
    """
    def __init__(self):
        primitive_util.ConvertibleDefaultDict.__init__(self, BuyStat)

def accum_buy_stats(games_stream, accum_stats, 
                    acceptable_deck_filter=lambda game, name: True,
                    max_games=-1):
    """ Accumulate buy statistics from games_stream into accum_stats.

    games_stream: an iterable of game.Game objects.
    accum_stats: DeckBuyStats object to store results.
    acceptable_deck_filter: predicate that determines if information about
      a particular deck should be included.  By default, include everything.
    """
    for idx, game_val in enumerate(games_stream):
        counted_game_len = False
        every_set_cards = card_info.EVERY_SET_CARDS
        supply_cards = set(game_val.get_supply()).union(every_set_cards)

        for changes in game_val.deck_changes_per_player():
            if not acceptable_deck_filter(game_val, changes.name):
                continue
            any_gained = set()
            win_points = game_val.get_player_deck(changes.name).WinPoints()

            for category in game.PlayerDeckChange.CATEGORIES:
                for card in getattr(changes, category):
                    getattr(accum_stats[card], category).AddOutcome(win_points)
                        
                    if category in ['gains', 'buys']:
                        any_gained.add(card)

            for card in any_gained:
                accum_stats[card].any_gained.AddOutcome(win_points)
            #for card in supply_cards - any_gained:
            #    accum_stats[card].none_gained.AddOutcome(win_points)

            all_avail = supply_cards.union(any_gained)
            for card in all_avail:
                accum_stats[card].available.AddOutcome(win_points)

            if not counted_game_len:  # don't double count this
                counted_game_len = True
                game_len = game_val.get_turns()[-1].get_turn_no()
                for card in supply_cards:
                    stats_obj = accum_stats[card]
                    stats_obj.game_length.AddOutcome(game_len)
                    if 'Colony' in game_val.get_supply():
                        stats_obj.game_length_colony.AddOutcome(game_len)

        if idx + 1 == max_games:
            break

def add_effectiveness(accum_stats, global_stats):
    """
    Add some statistics about a player's 'effectiveness' when they gain or
    don't gain the card.
    """
    # first, find the incremental effect of the player's skill
    any_eff = accum_stats['Estate'].available.mean_diff(
        global_stats['Estate'].available)

    for card in accum_stats:
        # now compare games in which the player gains/skips the card to gains
        # in which other players gain/skip the card
        stats_obj = accum_stats[card]
        global_stats_obj = global_stats[card]
        card_gain_eff = stats_obj.any_gained.mean_diff(
            global_stats_obj.any_gained)
        card_skip_eff = stats_obj.none_gained.mean_diff(
            global_stats_obj.none_gained)
        stats_obj.effectiveness_gain = card_gain_eff.mean_diff(any_eff)
        stats_obj.effectiveness_skip = card_skip_eff.mean_diff(any_eff)

def progress_meter(iterable, chunksize):
    """ Prints progress through iterable at chunksize intervals."""
    scan_start = time.time()
    since_last = time.time()
    for idx, val in enumerate(iterable):
        if idx % chunksize == 0 and idx > 0: 
            print idx
            print 'avg rate', idx / (time.time() - scan_start)
            print 'inst rate', chunksize / (time.time() - since_last)
            since_last = time.time()
            print
        yield val

def do_scan(scanner, games_col, accum_stats, max_games):
    """ Use scanner to accumulate stats from games_col into accum_stats .

    scanner: incremental_scanner.Scanner to use for traversal.
    games_col:  Mongo collection to scan.
    accum_stats: DeckBuyStats instance to store results.
    """
    def games_stream():
        for raw_game in progress_meter(scanner.scan(games_col, {}), 1000):
            yield game.Game(raw_game)
    accum_buy_stats(games_stream(), accum_stats, max_games=max_games)

def main():
    """ Scan and update buy data"""
    start = time.time()
    con = pymongo.Connection()
    games = con.test.games
    output_db = con.test

    parser = utils.incremental_parser()
    parser.add_argument('--max_games', default=-1, type=int)
    args = parser.parse_args()

    overall_stats = DeckBuyStats()

    scanner = incremental_scanner.IncrementalScanner('buys', output_db)
    buy_collection = output_db['buys']

    if not args.incremental:
        print 'resetting scanner and db'
        scanner.reset()
        buy_collection.drop()

    start_size = scanner.get_num_games()
    print scanner.status_msg()
    do_scan(scanner, games, overall_stats, args.max_games)
    print scanner.status_msg()
    end_size = scanner.get_num_games()

    if args.incremental:
        existing_overall_data = DeckBuyStats()
        utils.read_object_from_db(existing_overall_data, buy_collection, '')
        overall_stats.merge(existing_overall_data)
        def deck_freq(data_set):
            return data_set['Estate'].available.Frequency()
        print 'existing', deck_freq(existing_overall_data), 'decks'
        print 'after merge', deck_freq(overall_stats), 'decks'

    utils.write_object_to_db(overall_stats, buy_collection, '')

    scanner.save()
    time_diff = time.time() - start
    games_diff = end_size - start_size
    print ('took', time_diff, 'seconds for', games_diff, 'games for a rate of',
           games_diff / time_diff, 'games/sec')

def profilemain():
    """ Like main(), but print a profile report."""
    import hotshot, hotshot.stats
    prof = hotshot.Profile("buys.prof")
    prof.runcall(main)
    prof.close()
    stats = hotshot.stats.load("buys.prof")
    stats.strip_dirs()
    stats.sort_stats('time', 'calls')
    stats.print_stats(20)

if __name__ == '__main__':
    main()
    
