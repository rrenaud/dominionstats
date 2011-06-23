#!/usr/bin/python

import card_info
import game
import random
import utils

def long_deck_composition_list(d):
    ret = []
    for card in card_info.card_names():
        ret.append(d.get(card, 0))
    return ret

def encode_state_r_fmt(g, game_state):
    output_list = []
    output_list = [g.get_id() + str(game_state.turn_index())]
    turn_order = game_state.player_turn_order()
    output_list.append(g.get_player_deck(turn_order[0]).WinPoints())
    # print g.get_id(), g.get_player_deck(turn_order[0]).WinPoints()
    for player_name in turn_order:
        deck_comp = game_state.get_deck_composition(player_name)
        # need to get monument vp chips in this score.
        output_list.append(game.score_deck(deck_comp))
        output_list.extend(long_deck_composition_list(deck_comp))
    return output_list

def main():
    c = utils.get_mongo_connection()

    output_file = open('r_format.data', 'w')
    header = ['outcome']
    for player_label in ['s', 'o']:
        header.append(player_label + 'Score')
        for card in card_info.card_names():
            header.append(player_label + 
                          card.replace(' ', '_').replace("'", ''))
    output_file.write(' '.join(header) + '\n')
    
    for raw_game in utils.progress_meter(
        c.test.games.find({}).limit(10000), 1000):
        g = game.Game(raw_game)
        if g.dubious_quality() or len(g.get_player_decks()) != 2:
            continue

        encoded_states = []
        for game_state in g.game_state_iterator():
            encoded_state_list = encode_state_r_fmt(g, game_state)
            encoded_states.append(encoded_state_list)

        # only pick one state from each game to avoid overfitting.
        formatted_str = ' '.join(map(str, random.choice(encoded_states)))
        output_file.write(formatted_str)
        output_file.write('\n')
                          
                
if __name__ == '__main__':
    main()
