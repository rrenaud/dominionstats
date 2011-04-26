import csv
import os

_cardlist_reader = csv.DictReader(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'card_list.csv')))
_to_singular = {}
_to_plural = {}
_card_index = {}

_card_info_rows = {}

def _Init():
    for idx, cardlist_row in enumerate(_cardlist_reader):
        single, plural = cardlist_row['Singular'], cardlist_row['Plural']
        _to_singular[single] = single
        _to_singular[plural] = single
        _to_plural[single] = plural
        _to_plural[plural] = plural

        _card_index[single] = idx
        _card_info_rows[single] = cardlist_row

_Init()

def SingularOf(card_name):
    return _to_singular[card_name]

def PluralOf(card_name):
    return _to_plural[card_name]

def Pluralize(card, freq):
    return SingularOf(card) if freq == 1 else PluralOf(card)

def VPPerCard(singular_card_name):
    try:
        return int(_card_info_rows[singular_card_name]['VP'])
    except ValueError:
        return 0

def IsTreasure(singular_card_name):
    return _card_info_rows[singular_card_name]['Treasure'] == '1'

def Cost(singular_card_name):
    return _card_info_rows[singular_card_name]['Cost']

# Returns value of card name if the value is unambiguous.
def MoneyValue(card_name):
    try:
        return int(_card_info_rows[card_name]['Coins'])
    except ValueError, e:
        return 0

def IsVictory(singular_card_name):
    return _card_info_rows[singular_card_name]['Victory'] == '1'

def IsAction(singular_card_name):
    return _card_info_rows[singular_card_name]['Action'] == '1'

def NumCopiesPerGame(card_name, num_players):
    if IsVictory(card_name):
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


EVERY_SET_CARDS = ['Estate', 'Duchy', 'Province',
                   'Copper', 'Silver', 'Gold', 'Curse']

OPENING_CARDS = [card for card in _card_info_rows
                 if Cost(card) in ('0', '2', '3', '4', '5')]
OPENING_CARDS.sort()

def CardIndex(singular):
    return _card_index[singular]
