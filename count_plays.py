import pymongo
from collections import defaultdict
#module-level things like this can break
c = pymongo.Connection()
games = c.test.games

plays = c.test.plays
plays.ensure_index('key')
plays.ensure_index('cards')

plays_by_turn = c.test.plays_by_turn
plays_by_turn.ensure_index([('key', 1), ('turn', 1)])
plays_by_turn.ensure_index('cards')

BASIC_CARDS= ['Copper', 'Silver', 'Gold', 'Potion', 'Platinum',
               'Estate', 'Duchy', 'Province', 'Colony', 'Curse']

def analyze_plays():
    """
    Analyze the card plays in all games.
    """
    plays.remove()
    plays_by_turn.remove()
    counter = 0
    for game in games.find():
        counter += 1
        for deck in game['decks']:
            analyze_deck(deck)
        if counter % 10 == 0:
            print(counter)
        if counter % 1000 == 100:
            # instant gratification!
            compute_all_stats()

def compute_all_stats():
    """
    After analyze_plays has been run, augment the combo data with interesting
    statistics.
    """
    print('Collecting stats...')
    freqs = {}
    total_freqs = defaultdict(float)
    for combo in plays.find():
        cards = tuple(combo['cards'])
        freqs[cards] = combo['freq']
        total_freqs[len(cards)] += combo['freq']
    
    rates = {}
    for cards in freqs:
        rates[cards] = freqs[cards] / total_freqs[len(cards)]

    for collection in (plays, plays_by_turn):
        for combo in collection.find():
            freq = float(combo['freq'])
            cards = tuple(combo['cards'])
            interestingness = _relative_rate(cards, rates)

            # Interesting TODO: split the credit between multiple simultaneous
            # combos, instead of giving all of them all the credit
            combo['rate'] = rates[cards]
            combo['interestingness'] = interestingness
            combo['win_rate'] = combo['win_points'] / freq
            combo['vp_rate'] = combo['victory_points'] / freq
            combo['money_rate'] = combo['money'] / freq
            combo['combo_score'] = combo['interestingness'] * combo['win_rate']
            collection.save(combo)
    
def analyze_deck(deck):
    """
    Analyze the card plays in a single recorded deck, adding results to the
    `plays` and `plays_by_turn` collections.
    """
    win_points = deck['win_points']
    victory_points = deck['points']
    for turn in deck['turns']:
        money = turn.get('money', 0)
        plays = turn.get('plays', [])
        turn_number = turn['number']

        # Some bookkeeping to make sure we count repeated combos in a way
        # that matches intuition. For example:
        #   [Festival, Smithy] has 1 instance of the combo (Festival, Smithy)
        #   [Festival, Smithy, Smithy] also has 1 instance
        #   [Festival, Smithy, Festival, Smithy] has 2 instances
        multiplicity = defaultdict(int)
        for card in plays:
            if card not in BASIC_CARDS:
                multiplicity[card] += 1
        unique_plays = multiplicity.keys()
        unique_plays.sort()

        for i1, card1 in enumerate(unique_plays):
            _record_play((card1,), win_points, victory_points,
                         money, turn_number, multiplicity)
            for i2, card2 in enumerate(unique_plays[i1+1:]):
                _record_play((card1, card2),
                             win_points, victory_points,
                             money, turn_number, multiplicity)
                for i3, card3 in enumerate(unique_plays[i1+i2+2:]):
                    assert card3 != card1
                    assert card3 != card2
                    _record_play((card1, card2, card3),
                                 win_points, victory_points,
                                 money, turn_number, multiplicity)

def _record_play(cards, win_points, victory_points,
                 money, turn_number, multiplicity):
    occur = min(multiplicity[card] for card in cards)
    key = '+'.join(cards)
    
    increases = {'freq': occur,
                 'win_points': win_points * occur,
                 'victory_points': victory_points * occur,
                 'money': money * occur,
                }

    plays.update(
        {'key': key},
        {'$set': {'cards': list(cards), 'ncards': len(cards)},
         '$inc': increases},
        upsert=True,
        safe=False
    )
    #plays_by_turn.update(
    #    {'key': key, 'turn': turn_number},
    #    {'$set': {'cards': list(cards), 'ncards': len(cards)},
    #     '$inc': increases},
    #    upsert=True,
    #    safe=False
    #)

def _relative_rate(combo, rates):
    """
    How much more often than expected this combo is played.

    This is a quick hack for now. The functions for relative bigram and trigram
    frequency from NLP would be more effective, but I don't feel like looking
    them up and implementing them right now. --Rob
    """
    if len(combo) == 1:
        expected = 1.0
    elif len(combo) == 2:
        expected = rates[combo[0:1]] * rates[combo[1:2]]
    elif len(combo) == 3:
        expected = max(rates[(combo[0],)] * rates[(combo[1], combo[2])],
                       rates[(combo[1],)] * rates[(combo[0], combo[2])],
                       rates[(combo[2],)] * rates[(combo[0], combo[1])]
                      )
    #FIXME: this falls through if not 1/2/3
    return rates[combo] / expected

if __name__ == '__main__':
    print('Analyzing games...')
    analyze_plays()

