#!/usr/bin/python
# -*- coding: utf-8 -*-

""" Convert game documents to a format easily readable by R."""

import itertools

import card_info as ci
import game
import random
import sys
import utils

def nice_feature_name(n):
    return n.replace(' ', '_').replace("'", '')

def composition_deck_extractor(deck_comp, game_state, player):
    ret = []
    for card in ci.card_names():
        ret.append(deck_comp.get(card, 0))
    return ret
composition_deck_extractor.feature_names = map(nice_feature_name, 
                                               ci.card_names())

def score_deck_extractor(deck_comp, game_state, player):
    return [game_state.player_score(player)]

def deck_size_deck_extractor(deck_comp, game_state, player):
    return [sum(deck_comp.itervalues())]

def action_balance_deck_extractor(deck_comp, game_state, player):
    ret = 0.0
    for card, quant in deck_comp.iteritems():
        ret += (ci.num_plus_actions(card) - ci.is_action(card)) * quant
    return [ret / (sum(deck_comp.itervalues()) or 1)]

def unique_deck_extractor(deck_comp, game_state, player):
    return [len(deck_comp)]

def outcome_special_extractor(g, game_state):
    turn_order = game_state.player_turn_order()
    win_points = g.get_player_deck(turn_order[0]).WinPoints()
    return [win_points]

def turn_tiebreaker_common_extractor(g, game_state):
    current_turn_order = game_state.player_turn_order()
    return [g.get_player_deck(current_turn_order[0]).TurnOrder()]

def num_piles_empty_common_extractor(g, game_state):
    ret = 0
    for card, quant in game_state.supply.iteritems():
        if quant == 0:
            ret += 1
    return [ret]

def num_piles_low_common_extractor(g, game_state):
    ret = 0
    for card, quant in game_state.supply.iteritems():
        if quant <= 2:
            ret += 1
    return [ret]

def prov_or_colony_low_extractor(g, game_state):
    for card, quant in game_state.supply.iteritems():
        if (card == 'Province' or card == 'Colony') and 1 <= quant <= 2:
            return [1]
    return [0]

def turn_no_common_extractor(g, game_state):
    return [game_state.turn_index()]

def supply_common_extractor(g, game_state):
    ret = []
    for card in ci.card_names():
        ret.append(game_state.supply.get(card, 0))
    return ret
supply_common_extractor.feature_names = map(nice_feature_name, ci.card_names())

def make_extractor_list(suffix):
    extractor_names = [n[:-len(suffix)] for n in 
                       globals() if n.endswith(suffix)]
    extractors = [eval(n + suffix) for n in extractor_names]

    for extractor, name in itertools.izip(extractors, extractor_names):
        if not hasattr(extractor, 'feature_names'):
            extractor.feature_names = [name]
    return extractors

_deck_extractor_list = make_extractor_list('deck_extractor')
_common_extractor_list = make_extractor_list('common_extractor')

def feature_names(feature_extractor_list):
    ret = []
    for extractor in feature_extractor_list:
        ret.extend(extractor.feature_names)
    return ret

def state_to_features(g, game_state):
    output_list = []

    for common_extractor in _common_extractor_list:
        output_list.extend(common_extractor(g, game_state))
    
    per_player_features = []
    for player_name in game_state.player_turn_order():
        cur_player_features = []
        deck_comp = game_state.get_deck_composition(player_name)
        for extractor in _deck_extractor_list:
            cur_player_features.extend(
                extractor(deck_comp, game_state, player_name))
        output_list.extend(cur_player_features)
        per_player_features.append(cur_player_features)

    p1, p2 = per_player_features
    for p1_feature_val, p2_feature_val in itertools.izip(p1, p2):
        output_list.append(p1_feature_val - p2_feature_val)
    
    output_list.extend(outcome_special_extractor(g, game_state))
    return output_list

def output_state(state, output_file, sep=' '):
    formatted_str = sep.join(map(unicode, state))
    output_file.write(formatted_str)
    output_file.write('\n')

def output_vw_state(state, output_file):
    named_features = zip(all_feature_names, state)
    feature_str = ' '.join('%s:%s' % (feature, value)
                           for feature, value in named_features
                           if value and feature != "outcome_")
    outcome = state[-1]*2-1
    uid = random_id()
    formatted_str = "%s 1.0 %s|Features %s" % (outcome, uid, feature_str)
    print >> output_file, formatted_str

def convert_r_to_vw(input_file, output_file):
    global all_feature_names
    skipped_first = False
    for line in input_file:
        if skipped_first:
            state = map(int, line.strip().split())
            output_vw_state(state, output_file)
        else:
            all_feature_names = line.strip().split()
            skipped_first = True

def get_all_feature_names():
    header = feature_names(_common_extractor_list)
    
    for player_label in ['my', 'opp', 'diff']:
        for feature_name in feature_names(_deck_extractor_list):
            header.append(player_label + '_' + feature_name)
       
    header.append('outcome_')
    return header
all_feature_names = get_all_feature_names()

def random_id():
    return hex(random.randrange(0, 1<<32))[2:]

def write_r_header(output_file):
    outputted = ' '.join(get_all_feature_names()) + '\n'
    output_file.write(outputted)

def write_weka_header(output_file, force_classification):
    output_file.write('@RELATION isotropic_games\n\n')
    for feature_name in get_all_feature_names()[:-1]:
        output_file.write('@ATTRIBUTE %s NUMERIC\n' % feature_name)
    assert force_classification
    output_file.write('@ATTRIBUTE outcome_ {0,1}')
    output_file.write('\n@DATA\n')

def output_libsvm_state(state, output_file):
    if state[-1] == 0:
        output_file.write('-1 ')
    else:
        output_file.write('1 ')
    for index, value in enumerate(state[:-1]):
        if value != 0:
            output_file.write('%d:%d ' % (index + 1, value))
    output_file.write('\n')

def main():
    c = utils.get_mongo_connection()

    force_classification = True

    prefix = 'data/test_huge_'
    # limit = 10000
    r_output_file = open(prefix + 'r_format.data', 'w')
    weka_output_file = open(prefix + 'games.arff', 'w')
    vw_output_file = open(prefix + 'games.vw.txt', 'w')
    librf_output_file = open(prefix + 'librf_games.csv', 'w')
    librf_labels_file = open(prefix + 'librf_games_labels.txt', 'w')
    libsvm_output_file = open(prefix + 'libsvm_games.txt', 'w')
    write_r_header(r_output_file)
    write_weka_header(weka_output_file, force_classification)
    
    for raw_game in utils.progress_meter(
        c.test.games.find()
        ):
        g = game.Game(raw_game)
        if g.dubious_quality() or len(g.get_player_decks()) != 2:
            continue
        if force_classification and g.get_player_decks()[0].WinPoints() == 1.0:
            print 'skipping tie'

        saved_turn_ind = random.randint(0, len(g.get_turns()) - 1)
        for ind, game_state in enumerate(g.game_state_iterator()):
            # if ind == saved_turn_ind:
                encoded_state = state_to_features(g, game_state)
                if force_classification:
                    encoded_state[-1] = int(encoded_state[-1] / 2)
                #output_state(encoded_state, r_output_file, ' ')
                #output_state(encoded_state, weka_output_file, ',')

                #output_state(encoded_state[:-1], librf_output_file, ',')
                #librf_labels_file.write('%d\n' % encoded_state[-1])

                output_libsvm_state(encoded_state, libsvm_output_file)
                output_vw_state(encoded_state, vw_output_file)
        #else:
        #    assert False, ('did not find turn %d in %s' % (saved_turn_ind,
                                                           # game.get_id()))

def convert_main():
    infile = open('data/r_format.data')
    outfile = open('data/games.vw', 'w')
    convert_r_to_vw(infile, outfile)
    infile.close()
    outfile.close()
                
if __name__ == '__main__':
    main()
