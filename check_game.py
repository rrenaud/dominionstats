#!/usr/bin/python

from goals import *
import sys
from pprint import pprint

c = pymongo.Connection()
games_collection = c.test.games

for arg in sys.argv[1:]:
    gs = games_collection.find({'_id': arg})
    for g in gs:
        game_val = game.Game(g)

        for x in check_goals(game_val):
            print "%15s%20s%50s"%(x['goal_name'], x['player'], x['reason'])

