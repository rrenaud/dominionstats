#!/usr/bin/python

import pymongo
import card_info
import collections
import game
import incremental_scanner
import name_merger
import utils
import operator

# BOM: Bought only money and Victory.
# BOMMinator: Won buying only money and Victory.
# NegativeSum: Won with a negative score.
# Salted Earth: Had a negative score.
# PileDriver: Owned all copies of a card.

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

#("I thought it was Golf") Winning with a negative score
def CheckMatchGolfer(g):
    if g.any_resigned():
        return []
    ret = []
    for player in g.get_player_decks():
        if player.WinPoints() > 1.0 and player.Points() < 0:
            ret.append({'player': player.name(),
                        'reason': 'Won with a negative score, %d points' % (
                        player.Points())})
    return ret


def CheckMatchPileDriver(g):
    accumed_per_player = g.cards_accumalated_per_player()
    ret = []
    game_size = len(g.get_player_decks())
    for player, card_dict in accumed_per_player.iteritems():
        if g.get_player_deck(player).WinPoints() > 1.0:
            for card, quant in card_dict.iteritems():
                if quant == card_info.num_copies_per_game(card, game_size):
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


# buy 6 differently named Victory cards
def CheckMatchMrGreenGenes(g):
    accumed_per_player = g.cards_accumalated_per_player()
    ret = []
    for player, card_dict in accumed_per_player.iteritems():
        victory_quants = [(c, q) for c, q in card_dict.iteritems() if
                          card_info.is_victory(c)]
        if len(victory_quants) >= 6:
            ret.append({
                    'player': player,
                    'reason': 'Bought %d differently named Victory cards' %
                    len(victory_quants)}
                       )
    return ret

def CheckScore(g, low, high=None):
    ret = []
    for player in g.get_player_decks():
        score = player.points
        if score >= low and (high is None or score < high):
            ret.append({'player': player.name(),
                        'reason': "Scored more than %d points" % low})
    return ret

# Peer: Scored 60 points.
# Regent: Scored 70 points.
# Royal Heir: Scored 80 points.
# Monarch: Scored 90 points.
# Imperial: Scored 100 points.
# Archon: Scored 110 points.

def CheckMatchPeer(g):
    return CheckScore(g, 60, 70)

def CheckMatchRegent(g):
    return CheckScore(g, 70, 80)

def CheckMatchRoyalHeir(g):
    return CheckScore(g, 80, 90)

def CheckMatchMonarch(g):
    return CheckScore(g, 90, 100)

def CheckMatchImperial(g):
    return CheckScore(g, 100, 110)

def CheckMatchArchon(g):
    return CheckScore(g, 110)

def GroupFuncs(funcs, group_name):
    for idx, func in enumerate(funcs):
        func.group = group_name
        func.priority = idx

GroupFuncs([CheckMatchPeer, CheckMatchRegent, CheckMatchRoyalHeir,
            CheckMatchMonarch, CheckMatchImperial, CheckMatchArchon], 'vp')

# == How the game ends
#("Buzzer Beater") Winning by exactly one point
def CheckMatchBuzzerBeater(g):
    scores = {}
    for player in g.get_player_decks():
        score = player.points
        scores[player.name()] = score
    s_scores = sorted(scores.iteritems(), key=operator.itemgetter(1), reverse=True)
    if len(s_scores)>1 and s_scores[0][1] == s_scores[1][1] + 1:
        return [{'player': s_scores[0][0],
                 'reason': "Won by exactly one point"}]

# Anticlimactic - shared a victory with two or more opponents
def CheckMatchAnticlimactic(g):
    num_players = len(g.get_player_decks())

    if num_players == 3:
        max_score = 1.0
    elif num_players == 4:
        max_score = 4.0/3
    else:
        return []

    ret = []
    for player in g.get_player_decks():
        wp = player.WinPoints()
        if wp>max_score:
            return ret
        elif wp!=0.0:
            ret.append( {'player': player.name(), 'reason': 'Shared a victory with two or more opponents'} )
    print ret
    return ret


#("The Biggest Loser") Losing with over 60 points.
# Surprise Attack - end the game on supply piles when those three piles had totaled at least 5 cards at the start of your turn.
# Badges? We Don't Need No Stinking Badges: Win a game while holding no VP Tokens and your opponent holds 25 or more.

# == How the game ends
#("Penny Pincher") Winning by buying out the Coppers
#("Estate Sale") Winning by buying out the Estates

# == Value of victory points

# Carny - at least 30 VP from Fairgrounds
# Original suggestion: Blue ribbon - ended game with a Fairgrounds worth 8 VP
def CheckMatchCarny(g):
    ret = []
    for player, deck in g.cards_accumalated_per_player().iteritems():
        if 'Fairgrounds' not in deck:
            continue
        fg_pts = game.score_fairgrounds(deck)
        if fg_pts >= 30:
            ret.append( {'player': player, 'reason': '%d VP from Fairgrounds' % fg_pts} )
    return ret


# Gardener - at least 20 VP from Gardens
# Original suggestion: ended game with a Gardens worth 6 VP
def CheckMatchGardener(g):
    ret = []
    for player, deck in g.cards_accumalated_per_player().iteritems():
        if 'Gardens' not in deck:
            continue
        g_pts = game.score_gardens(deck)
        if g_pts >= 20:
            ret.append( {'player': player, 'reason': '%d VP from Gardens' % g_pts} )

    return ret

# Duke of Earl
# Original suggestion Duchebag :-) - at least 42 points from dukes and duchies alone
def CheckMatchDukeOfEarl(g):
    ret = []
    for player, deck in g.cards_accumalated_per_player().iteritems():
        if 'Duke' not in deck:
            continue
        duke_pts = game.score_duke(deck)
        duchy_pts = deck['Duchy'] * 5
        d_pts = duke_pts + duchy_pts
        if d_pts >= 42:
            ret.append( {'player': player, 'reason': '%d VP from Dukes and Duchies' % d_pts} )
    return ret

# == Use of one card in a turn
#("Puppet Master") Play more than 4 Possession in one turn.
# Crucio: Use the Torturer three times in a single turn.
# Imperio: Use Possession three times in a single turn.

# == Every Turn
# Protego: Reacted to all attacks against you (and at least 5).
#("Bully") Play an attack every turn after the fourth.
# Empty Throne Room
# Empty Kings Court


# == Number of Cards acquired
# King of the Joust - acquire all five prizes
# Researcher: Acquire 7 Alchemists or Laboratories.
# Evil Overlord: Acquire 7 or more Minions.
# It's Good to be the King: Acquire 4 Throne Rooms or King's Courts.
# 99 Problems: Acquire the majority of Harems.
# Game of Settlers Anyone?: Acquire 7 of a single Village-type card.
# won without ever buying money
#("Dominator") Have at least one of each type of available victory card (and at least 1 chip, if available).
# buying at least one of every kingdom card in a game

# == Specific Uses
# Used Possession+Masquerade to send yourself a Province or Colony
# gifted a Province or Colony to an opponent (through Masquerade or Ambassador),
# De-model - remodeled a card into a card that costs less
# Banker - played a Bank worth $10
# Look Out! - revealed three 6+-cost cards with Lookout
# Goon Squad - acquired 42 VP tokens from Goons in a single turn
# played 20 actions in a turn

#("This card sucks?") Winning with an Opening Chancellor


def CheckPointsPerTurn(g, low, high=None):
    ret = []
    scores = []
    players = g.all_player_names()
    for state in g.game_state_iterator():
        score = []
        for p in players:
            score.append(state.player_score(p))
        scores.append(score)

    for (i,p) in enumerate(players):
        for turn_no in range(i, len(scores)-1, len(players)):
            gain = scores[turn_no+1][i] - scores[turn_no][i]
            if gain >= low and (high is None or gain < high):
                ret.append({
                        'player': p,
                        'reason': "Scored %d or more points in one turn" %
                        low})
    return ret

#Slam: 20 or more points in one turn.
#Crash: 30 or more points in one turn.
#Charge: 40 or more points in one turn.
#KO: 50 or more points in one turn.
#Blitz: 60 or more points in one turn.
#Onslaught: 70 or more points in one turn.
def CheckMatchSlam(g):
    return CheckPointsPerTurn(g, 20, 30)

def CheckMatchCrash(g):
    return CheckPointsPerTurn(g, 30, 40)

def CheckMatchCharge(g):
    return CheckPointsPerTurn(g, 40, 50)

def CheckMatchKO(g):
    return CheckPointsPerTurn(g, 50, 60)

def CheckMatchBlitz(g):
    return CheckPointsPerTurn(g, 60, 70)

def CheckMatchOnslaught(g):
    return CheckPointsPerTurn(g, 70)

GroupFuncs([CheckMatchSlam, CheckMatchCrash, CheckMatchCharge, CheckMatchKO,
            CheckMatchBlitz, CheckMatchOnslaught], 'vp_turn')

#Mega-Turn: you buy all the starting Provinces (or Colonies) in a single turn.
def CheckMatchMegaTurn(g):
    ret = []
    scores = []
    if 'Colony' in g.get_supply():
        biggest_victory = 'Colony'
    else:
        biggest_victory = 'Province'

    victory_copies = card_info.num_copies_per_game(biggest_victory,
                                                   len(g.get_player_decks()))
    for turn in g.get_turns():
        new_cards = turn.buys + turn.gains
        if len(new_cards) < victory_copies:
            continue
        if new_cards.count(biggest_victory) == victory_copies:
            ret.append(
                {'player': turn.player.name(),
                 'reason': "Obtained all of the %s cards in one turn" %
                 biggest_victory})
    return ret

#("Oscar The Grouch") Trash more than 7 cards in one turn
def CheckMatchOscarTheGrouch(g):
    ret = []
    for turn in g.get_turns():
        trashes = len(turn.turn_dict.get('trashes',[]))
        if trashes >= 7:
            ret.append({'player': turn.player.name(),
                        'reason': "Trashed %d cards in one turn" % trashes})
    return ret

goal_check_funcs = {}

for name in dict(globals()):
    if name.startswith('CheckMatch'):
        goal = name[len('CheckMatch'):]
        goal_func = globals()[name]
        goal_check_funcs[goal] = goal_func
        if not hasattr(goal_func, 'group'):
            goal_func.group = 'ungrouped'
            goal_func.priority = 0

def GetGoalImageFilename(goal_name):
    return 'static/images/%s.png' % goal_name

def MaybeRenderGoals(db, norm_target_player):
    goal_matches = list(db.goals.find(
            {'attainers.player': norm_target_player}).
                        sort('_id', pymongo.DESCENDING))
    ret = ''

    if goal_matches:
        goals_achieved_freq = collections.defaultdict(int)
        ret += '<h2>Goals achieved</h2>\n'

        def GroupAndPriority(goal_match_doc):
            func = goal_check_funcs[goal_match_doc['goal']]
            return func.group, func.priority

        goal_matches.sort(key = GroupAndPriority)

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
                        img_loc = GetGoalImageFilename(goal_name)
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

def print_totals(checker_output, total):
    for goal_name, output in sorted(checker_output.iteritems(),
                                    key=lambda t: len(t[1]), reverse=True):
        print "%-15s %8d %5.2f" % (goal_name, len(output),
                                   len(output) / float(total))

def all_goals(game_val):
    goals = {}
    for goal_name, goal_checker in goal_check_funcs.iteritems():
        output = goal_checker(game_val)
        if output:
            goals[goal_name] = output
    return goals


def main():
    c = pymongo.Connection()
    games_collection = c.test.games
    output_collection = c.test.goals
    total_checked = 0

    checker_output = collections.defaultdict(list)

    parser = utils.incremental_max_parser()
    args = parser.parse_args()

    scanner = incremental_scanner.IncrementalScanner('goals', c.test)
    if not args.incremental:
        scanner.reset()
        output_collection.remove()
    output_collection.ensure_index('attainers.player')
    output_collection.ensure_index('goal')

    print 'starting with id', scanner.get_max_game_id(), 'and num games', \
        scanner.get_num_games()
    for g in utils.progress_meter(scanner.scan(games_collection, {})):
        total_checked += 1
        game_val = game.Game(g)
        for goal_name, output in all_goals(game_val).items():
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
    print_totals(checker_output, total_checked)


if __name__ == '__main__':
    main()
