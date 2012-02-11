#!/usr/bin/python

from goals import *
import sys

def main(n):
    c = pymongo.Connection()
    games_collection = c.test.games
    output_collection = c.test.goals
    total_checked = 0

    checker_output = collections.defaultdict(int)

    parser = utils.incremental_max_parser()

    output_collection.ensure_index('attainers.player')
    output_collection.ensure_index('goal')

    recent_games = list(c.test.games.find(limit=n, sort=[('_id', pymongo.DESCENDING)]))

    for g in recent_games:
        total_checked += 1
        game_val = game.Game(g)
        for goals in check_goals(game_val):
            goal_name = goals['goal_name']
            checker_output[goal_name]+=1

    print_totals(checker_output, total_checked)


if __name__ == '__main__':
    if len(sys.argv)>1:
        n = int(sys.argv[1])
    else:
        n = 1000
    main(n)
