import csv
import os

_cardlist_reader = csv.DictReader(open(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'card_list.csv')))
_to_singular = {}
_to_plural = {}
_card_index = {}

_card_info_rows = []
# the way this file is being used, it seems like a good candidate for some sort
# of Card class with properties, etc
def _init():
    for idx, cardlist_row in enumerate(_cardlist_reader):
        single, plural = cardlist_row['Singular'], cardlist_row['Plural']
        _to_singular[single] = single
        _to_singular[plural] = single
        _to_plural[single] = plural
        _to_plural[plural] = plural

        _card_index[single] = idx
        _card_info_rows.append(cardlist_row)

        var_name = single.replace("'", '').replace(' ', '_').upper()
        globals()[var_name] = idx

_init()

def singular_of(card_name):
    return _to_singular[card_name]

def plural_of(card_name):
    return _to_plural[card_name]

def pluralize(card, freq):
    return singular_of(card) if freq == 1 else plural_of(card)

def vp_per_card(card_id):
    assert type(card_id) == int
    try:
        return int(_card_info_rows[card_id]['VP'])
    except ValueError:
        return 0

def is_treasure(card_id):
    assert type(card_id) == int
    return _card_info_rows[card_id]['Treasure'] == '1'

def cost(card_id):
    assert type(card_id) == int
    return _card_info_rows[card_id]['Cost']

# Returns value of card name if the value is unambiguous.
def money_value(card_id):
    assert type(card_id) == int
    try:
        return int(_card_info_rows[card_id]['Coins'])
    except ValueError, e:
        return 0

def is_victory(card_id):
    assert type(card_id) == int
    return _card_info_rows[card_id]['Victory'] == '1'

def is_action(card_id):
    assert type(card_id) == int
    return _card_info_rows[card_id]['Action'] == '1'

def num_copies_per_game(card_id, num_players):
    assert type(card_id) == int
    if is_victory(card_id):
        if num_players >= 3:
            return 12
        return 8
    if card_id == CURSE:
        return 10 * (num_players - 1)
    return {POTION: 16,
            PLATINUM: 12,
            GOLD: 30,
            SILVER: 40,
            COPPER: 60
            }.get(card_id, 10)

TOURNAMENT_WINNINGS = [PRINCESS, DIADEM, FOLLOWERS, TRUSTY_STEED, BAG_OF_GOLD]

EVERY_SET_CARDS = [ESTATE, DUCHY, PROVINCE, 
                   COPPER, SILVER, GOLD, CURSE]

OPENING_CARDS = [card_id for card_id in xrange(len(_card_info_rows))
                 if cost(card_id) in ('0', '2', '3', '4', '5')]
OPENING_CARDS.sort()

def card_index(singular):
    return _card_index[singular]

def card_from_index(idx):
    return _card_info_rows[idx]

def card_name(idx):
    return card_from_index(idx)['Singular']

def card_names(card_inds):
    return map(card_name, card_inds)
