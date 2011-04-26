#!/usr/bin/python

import os
import pymongo
import re
import sys

import argparse
import utils

parser = utils.incremental_date_range_cmd_line_parser()

def main():
    args = parser.parse_args()
    games_table = pymongo.Connection().test.games
    games_table.ensure_index('players')
    games_table.ensure_index('supply')
    data_files_to_load = os.listdir('parsed_out')
    data_files_to_load.sort()
    find_id = re.compile('game-.*.html')
    done = set()
    for fn in data_files_to_load:
        yyyymmdd = fn[:8]
        print yyyymmdd
        if not utils.includes_day(args, yyyymmdd):
            print 'skipping', fn, 'because not in range'
            continue

        if args.incremental:
            if yyyymmdd in done:
                print 'skipping', fn, 'because done'
                continue
            contents = open('parsed_out/' + fn, 'r').read(100)
            if contents.strip() == '[]':
                print "empty contents (make parser not dump empty files?)", \
                      fn
                continue
            first_game_id_match = find_id.search(contents)
            assert first_game_id_match is not None, (
                'could not get id from %s in file %s' % (contents, fn))
            first_game_id = first_game_id_match.group(0)
            query = {'_id': first_game_id}
            if games_table.find(query).count():
                done.add(yyyymmdd)
                print 'skipping', yyyymmdd, 'and marking as done'
                continue
            else:
                print first_game_id, str(query), 'not in db, importing'
        
        cmd = ('mongoimport -h localhost parsed_out/%s -c '
               'games --jsonArray' % fn)
        print cmd
        os.system(cmd)

if __name__ == '__main__':
    main()
