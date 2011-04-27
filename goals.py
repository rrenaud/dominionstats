#!/usr/bin/python

import pymongo
import game
import card_info
import collections
import name_merger
import incremental_scanner

# BOM: Bought only money and Victory.
# BOMMinator: Won buying only money and Victory.
# NegativeSum: Won with a negative score.
# Salted Earth: Had a negative score.
# PileDriver: Owned all copies of a card.
# Protego: Reacted to all attacks against you (and at least 5).
# OneTrickPony: Bought seven or more of one card and no other cards.
# Peer: Scored 60 points.
# Regent: Scored 70 points.
# Royal Heir: Scored 80 points.
# Monarch: Scored 90 points.
# Imperial: Scored 100 points.
# Archon: Scored 110 points.
 
# def CheckMatchGreenMonster(g):
#     last_turn = g.Turns()[-1]
#     if last_turn.Player().WinPoints() > 1:
#         accumed = last_turn.PlayerAccumulates()
#         big_vp_cards = 0
#         total_vp_cards = 0
        
#         for card in accumed:
#             card_vp = card_info.VPPerCard(card)
#             if card_vp:
#                 total_vp_cards += 1
#                 if card_vp >= 6:
#                     big_vp_cards += 1
#             if big_vp_cards >= 3 and total_vp_cards >= 8:
#                 return [last_turn.Player().Name()]
#     return []
#FIXME: this is still a Work in Progress unfortunately
def CheckMatchBOM(g):
    ret = []
    cards_per_player = g.cards_accumalated_per_player()
    for player, card_list in cards_per_player.iteritems():
        treasures = []
        bad = False
        if g.get_player_deck(player).Resigned():
            continue
        for card in card_list:
            if card_info.is_action(card):
                bad = True
                break
            if card_info.is_treasure(card):
                treasures.append(card)
        if not bad:
            ret.append({'player': player,
                        'reason': 'Bought only money and vp : %s' % (
                        ', '.join(treasures))
                        })
    return ret

def CheckMatchBOMMinator(g):
    cands = CheckMatchBOM(g)
    ret = []
    for match_dict in cands:
        player = match_dict['player']
        if g.get_player_deck(player).WinPoints() > 1.0:
            ret.append({'player': player, 
                        'reason' : match_dict['reason'] + ' and won'
                        })
    return ret

def CheckMatchNegativeSum(g):
    if g.any_resigned():
        return []
    ret = []
    for player in g.get_player_decks():
        if player.WinPoints() > 1.0 and player.Points() < 0:
            ret.append({'player': player.Name(),
                        'reason': 'Won with a negative score, %d points' % (
                        player.Points())})
    return ret

def CheckMatchPileDriver(g):
    accumed_per_player = g.cards_accumalated_per_player()
    ret = []
    for player, card_dict in accumed_per_player.iteritems():
        if g.get_player_deck(player).WinPoints() > 1.0:
            for card, quant in card_dict.iteritems():
                if quant == card_info.num_copies_per_game(card,
                                                       len(g.get_player_decks())):
                    ret.append(
                        {'player': player, 
                         'reason': 'Bought all %d copies of %s' % (
                                quant, card)}
                        )
    return ret

def CheckMatchOneTrickPony(g):
    accumed_per_player = g.cards_accumalated_per_player()
    ret = []
    for player, card_dict in accumed_per_player.iteritems():
        if g.get_player_deck(player).WinPoints() > 1.0:
            actions_quants = [(c, q) for c, q in card_dict.iteritems() if
                              card_info.is_action(c)]
            if len(actions_quants) != 1:
                continue
            if actions_quants[0][1] < 7:
                continue
            action, quant = actions_quants[0]
            ret.append({'player': player,
                        'reason': 'Bought no action other than %d %s' % (
                        quant, card_info.pluralize(action, quant))})
    return ret
            
                

def MaybeRenderGoals(db, norm_target_player):
    goal_matches = list(db.goals.find(
            {'attainers.player': norm_target_player}).
                        sort('_id', pymongo.DESCENDING))
    ret = ''
    if goal_matches:
        goals_achieved_freq = collections.defaultdict(int)
        ret += '<h2>Goals achieved</h2>\n'
        
        for goal_match_doc in goal_matches:
            for attainer in goal_match_doc['attainers']:
                if attainer['player'] == norm_target_player:
                    goals_achieved_freq[goal_match_doc['goal']] += 1

        seen_goal_yet = set()
        ret += '<ul style="list-style-type: none;">\n'
        for goal_match_doc in goal_matches:
            for attainer in goal_match_doc['attainers']:
                if attainer['player'] == norm_target_player:
                    goal_name = goal_match_doc['goal']
                    if goal_name not in seen_goal_yet:
                        seen_goal_yet.add(goal_name)
                        game_id = goal_match_doc['_id']
                        reason = ''
                        if attainer.has_key('reason'):
                            reason = ' : ' + attainer['reason']
                        freq = goals_achieved_freq[goal_name]
                        img_loc = 'static/images/%s.png' % goal_name
                        ret += (
                            '<li style="float: left;">'
                            '%s<img src="%s" title="%s%s"></a><br>' % 
                            (game.Game.get_councilroom_link_from_id(game_id),
                             img_loc, goal_name, reason))
                        if freq > 1:
                            ret += '%d times\n' % freq
        ret += '</ul>'
        ret += '<div style="clear: both;">&nbsp;</div>'
    return ret

def main():
    c = pymongo.Connection()
    games_collection = c.test.games
    output_collection = c.test.goals
    total_checked = 0

    goal_check_funcs = []
    checker_output = collections.defaultdict(list)
    for name in globals():
        if name.startswith('CheckMatch'):
            goal = name[len('CheckMatch'):]
            #FIXME: this is nonobvious
            checker_output[goal]
            goal_check_funcs.append((goal, globals()[name]))

    output_collection.ensure_index('attainers.player')
    output_collection.ensure_index('goal')
    scanner = incremental_scanner.IncrementalScanner('goals', c.test)
    print 'starting with id', scanner.get_max_game_id(), 'and num games', \
        scanner.get_num_games()
    for idx, g in enumerate(scanner.scan(games_collection, {})):
        if idx % 1000 == 0:
            print idx
        total_checked += 1
        game_val = game.Game(g)
        for goal_name, goal_checker in goal_check_funcs:
            output = goal_checker(game_val)
            if output:
                for attainer in output:
                    attainer['player'] = name_merger.norm_name(
                        attainer['player'])
                checker_output[goal_name].append(
                    (game_val.isotropic_url(), output))
                mongo_val = {'_id': game_val.get_id(),
                             'goal': goal_name,
                             'attainers': output}
                output_collection.save(mongo_val)

    print 'ending with id', scanner.get_max_game_id(), 'and num games', \
        scanner.get_num_games()
    scanner.save()

    for goal_name, output in checker_output.iteritems():
        print goal_name, len(output)

if __name__ == '__main__':
    main()
