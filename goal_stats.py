#!/usr/bin/python

import pymongo
import collections
import operator
import goals
import incremental_scanner

if __name__ == '__main__':
	c = pymongo.Connection()
	goal_db = c.test.goals
	gstats_db = c.test.goal_stats
	all_goals = goals.goal_check_funcs.keys()
	total_pcount = collections.defaultdict(int)
        goal_scanner = incremental_scanner.IncrementalScanner('goals', c.test)
        stat_scanner = incremental_scanner.IncrementalScanner('goal_stats', c.test)

	if goal_scanner.get_max_game_id() == stat_scanner.get_max_game_id():
		print "Stats already set! Skip"
		exit(0)

	for goal_name in all_goals:
		found_goals = list(goal_db.find({'goals.goal_name': goal_name}))
		total = len(found_goals)
		print goal_name, total

		pcount = collections.defaultdict(int)
		for goal in found_goals:
			player = goal['goals'][0]['player']
			pcount[player] += 1
			total_pcount[player] += 1


		psorted = sorted(pcount.iteritems(), key=operator.itemgetter(1), reverse=True)
		top = []
		leaders = 0
		i = 0
		while leaders<3 and i < len(psorted):
			(player, count) = psorted[i]
			players = [player]
			i += 1
			while i < len(psorted) and psorted[i][1] == count:
				players.append(psorted[i][0])
				i += 1
			leaders += len(players)
			top.append((players, count))
			
		mongo_val = {'_id': goal_name, 'count': total, 'top': top}
		gstats_db.save(mongo_val)

	stat_scanner.set_max_game_id(goal_scanner.get_max_game_id())
	stat_scanner.save()

"""  # Un-integrated code for top goal scorers
        player_scores = {}
        tot_games = float(db.games.count())
        for player in attainments_by_player:
            score = 0
            player_goal_freqs = attainments_by_player[player]
            for goal in player_goal_freqs:
                global_rareness = tot_games / goal_freq[goal]
                player_goal_freq = player_goal_freqs[goal]
                score += global_rareness / (1 + math.exp(-player_goal_freq))
            player_scores[player] = score

        goal_freq = goal_freq.items()
        goal_freq.sort(key = lambda x: x[1])

        ret = ''
        for goal, freq in goal_freq:
            ret += goal + ' ' + str(freq) + '<br>'

        ret += '<br>'
        player_scores = player_scores.items()
        player_scores.sort(key = lambda x: -x[1])
        for player, score in player_scores[:10]:
            ret += player + ' ' + '%.3f' % score + '<br>'

"""
