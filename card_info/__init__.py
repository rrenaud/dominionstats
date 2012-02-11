import csv
import os

_cardlist_reader = csv.DictReader(open(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'card_list.csv')))
_to_singular = {}
_to_plural = {}
_card_index = {}

_card_info_rows = {}
_card_names = []
_card_var_names = []

# the way this file is being used, it seems like a good candidate for some sort
# of Card class with properties, etc
def _init():
    for cardlist_row in _cardlist_reader:
        single, plural = cardlist_row['Singular'], cardlist_row['Plural']
        _to_singular[single] = single
        _to_singular[plural] = single
        _to_plural[single] = plural
        _to_plural[plural] = plural

        _card_index[single] = int(cardlist_row['Index'])
        _card_info_rows[single] = cardlist_row
        _card_names.append(single)
    _card_names.sort(key = lambda x: _card_index[x])
    for c in _card_names:
        _card_var_names.append(c.lower().replace(
                ' ', '_').replace('-', '_').replace("'", ''))

_init()

def singular_of(card_name):
    return _to_singular[card_name]

def plural_of(card_name):
    return _to_plural[card_name]

def pluralize(card, freq):
    return singular_of(card) if freq == 1 else plural_of(card)

def vp_per_card(singular_card_name):
    try:
        return int(_card_info_rows[singular_card_name]['VP'])
    except ValueError:
        return 0

def is_treasure(singular_card_name):
    return _card_info_rows[singular_card_name]['Treasure'] == '1'

def cost(singular_card_name):
    return _card_info_rows[singular_card_name]['Cost']

# Returns value of card name if the value is unambiguous.
def money_value(card_name):
    try:
        return int(_card_info_rows[card_name]['Coins'])
    except ValueError, e:
        return 0

def is_victory(singular_card_name):
    return _card_info_rows[singular_card_name]['Victory'] == '1'

def is_action(singular_card_name):
    return _card_info_rows[singular_card_name]['Action'] == '1'

def is_attack(singular_card_name):
    return _card_info_rows[singular_card_name]['Attack'] == '1'

def num_plus_actions(singular_card_name):
    r = _card_info_rows[singular_card_name]['Actions']
    try:
        return int(r)
    except ValueError:
        # variable number of plus actions, just say 1
        return 1

def num_copies_per_game(card_name, num_players):
    if is_victory(card_name):
        if num_players >= 3:
            return 12
        return 8
    if card_name == 'Curse':
        return 10 * (num_players - 1)
    return {'Potion': 16,
            'Platinum': 12,
            'Gold': 30,
            'Silver': 40,
            'Copper': 60
            }.get(card_name, 10)

TOURNAMENT_WINNINGS = ['Princess', 'Diadem', 'Followers', 
                       'Trusty Steed', 'Bag of Gold']

EVERY_SET_CARDS = ['Estate', 'Duchy', 'Province',
                   'Copper', 'Silver', 'Gold', 'Curse']

OPENING_CARDS = [card for card in _card_info_rows
                 if cost(card) in ('0', '2', '3', '4', '5')]
OPENING_CARDS.sort()

def sane_title(card):
    return card.title().replace("'S", "'s").replace(' Of ', ' of ').strip()

def card_index(singular):
    return _card_index[singular]

def card_names():
    return _card_names

def card_var_names():
    return _card_var_names
