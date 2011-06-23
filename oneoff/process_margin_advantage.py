import collections
import random

GameTup = collections.namedtuple('GameTup', ['margin',  'supply', 'names'])

def analyze(games):
    length = len(games)
    median = length / 2 
    median_margin = games[median].margin
    first_0, last_0 = -1, -1
    for ind, game_tup in enumerate(games):
        if game_tup.margin == 0:
            if first_0 == -1:
                first_0 = ind
            last_0 = ind
    def perc(f):
        return 100.0 * float(f) / length
    return median_margin, perc(first_0), perc(last_0)

def resample(games):
    """ Get rid of the second player is better skill bias in iso games.

    For each pair of opponents, only the minimum number of games in which each
    player is first is retained."""
    by_player_pair = collections.defaultdict(list)
    for game_tup in games:
        by_player_pair[tuple(sorted(game_tup.names))].append(game_tup)

    resampled = []
    for player_pair_tup, game_list in by_player_pair.iteritems():
        by_start_player = collections.defaultdict(list)
        for game_tup in game_list:
            by_start_player[game_tup.names[0]].append(game_tup)
        if len(by_start_player) != 2: 
            continue
        fewest_starts, most_starts = sorted(by_start_player.values(), key=len)
        resampled.extend(fewest_starts)
        resampled.extend(random.sample(most_starts, len(fewest_starts)))
    print 'from', len(games), 'sampled down to', len(resampled)
    return resampled

def analyze_by_card(games):
    ret = {}
    games.sort()
    ret['*all'] = analyze(games)
    by_card = collections.defaultdict(list)
    for game_tup in games:
        for card in game_tup.supply:
            by_card[card].append(game_tup)
    for card, sub_game_list in by_card.iteritems():
        ret[card] = analyze(sub_game_list)
    return ret

def main():
    games = []
    for line_idx, line in enumerate(open('margin.txt', 'r')):
        try:
            split_line = line.strip().split(':')
            if len(split_line) > 3:
                continue
            names = split_line[1]
            split_names = names.split(',')
            if len(split_names) != 2:
                continue
            games.append((GameTup(float(split_line[0]),
                                  split_line[2].split(','),
                                  split_names)))
        except IndexError:
            print line        

    full_sample_output = analyze_by_card(games)
    debiased_sample_output = analyze_by_card(resample(games))
    for key in sorted(full_sample_output.keys()):
        full_data = full_sample_output[key]
        unbias_data = debiased_sample_output[key]
        bias_margin = full_data[0]
        unbias_margin = unbias_data[0]
        def nice_float(f):
            return ('%.1f' % f).ljust(8)
        print '%s %s%s' % (key.ljust(30), 
                           nice_float(bias_margin), 
                           nice_float(unbias_margin))

if __name__ == '__main__':
    main()

