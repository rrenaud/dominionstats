from utils import get_mongo_connection
from game import Game, PlayerDeck
import card_info
from bolt.io import Dataset, dense2sparse
from bolt.trainer.sgd import SGD, Log
from bolt.model import LinearModel
from collections import defaultdict
import math
import numpy as np
from pymongo import ASCENDING, DESCENDING

con = get_mongo_connection()
DB = con.test

MAX_TURNS = 40
REQUIRED_PLAYERS = 2

CARDS = sorted(card_info._card_info_rows.keys())
CARDS_INDEX = {}
for i, card in enumerate(CARDS):
    CARDS_INDEX[card] = i
NCARDS = len(CARDS)

def logit(x):
    return 1.0 / (1.0 + math.exp(-x))

def vp_only(deck):
    newdeck = {}
    for card in deck:
        if card_info.IsVictory(card) or card == u'Curse':
            newdeck[card] = deck[card]
    return newdeck

def decks_by_turn(game):
    turn_ordered_players = sorted(game.PlayerDecks(),
                                  key=PlayerDeck.TurnOrder)
    nplayers = len(turn_ordered_players)
    turn_num = 1
    player_num = 0
    for state in game.GameStateIterator():
        player = turn_ordered_players[player_num].player_name
        balanced_points = turn_ordered_players[player_num].WinPoints() - 1
        yield (turn_num, state.player_decks[player], balanced_points)

        player_num += 1
        if (player_num == nplayers):
            player_num = 0
            turn_num += 1
        if turn_num > MAX_TURNS:
            break


def deck_to_vector(deck):
    vec = np.zeros((NCARDS,))
    for card, count in deck.items():
        idx = CARDS_INDEX[card]
        vec[idx] = count
    if np.sum(vec) == 0:
        # watch out for the masquerade trick
        return zero_vector()
    else:
        return vec / np.sum(vec)

def zero_vector():
    return np.zeros((NCARDS,))

def should_learn(game):
    return (len(game.player_decks) == REQUIRED_PLAYERS and
            game.player_decks[0].win_points != 1.0)

class IsotropicDataset(Dataset):
    def __init__(self, which_games, turn):
        self.games = which_games.find().sort('_id', DESCENDING)
        self.turn = turn
        self.n = which_games.count()
    def __iter__(self):
        counter = 0
        for gamedata in self.games:
            game = Game(gamedata)
            if should_learn(game):
                turn_vec = zero_vector()
                turn_count = 0
                for turn_num, deck_state, points in decks_by_turn(game):
                    if turn_num == self.turn:
                        vec = deck_to_vector(deck_state)
                        turn_count += 1
                        turn_vec += vec * points
                if turn_count == REQUIRED_PLAYERS and not np.all(turn_vec == 0.0):
                    yield (dense2sparse(turn_vec), 1)
                    yield (dense2sparse(-turn_vec), 0)
    def shuffle(self):
        self.games.shuffle()

def run_sgd(turn):
    classifier = SGD(loss=Log(), reg=0.0001, epochs=1)
    data = IsotropicDataset(DB.games, turn)
    model = LinearModel(NCARDS)
    classifier.train(model, data, verbose=1, shuffle=False)
    results = zip(model.w, CARDS)
    out = open('static/output/card-values-%d.txt' % turn, 'w')
    print >> out, results
    results.sort()
    for value, card in results:
        print "%20s\t% 4.4f" % (card, value)
    out.close()

if __name__ == '__main__':
    for turn in (10,):
        print "turn = %d" % turn
        run_sgd(turn)
