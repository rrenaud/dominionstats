#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
import os
import name_merger
import pymongo
import bz2

def main():
    filename_pattern = re.compile('^(?P<date>\d\d\d\d-\d\d-\d\d)\.html\.bz2$')
    leaderboard_pattern = re.compile('<td>(?P<skill_mean>-?\d+\.\d+) &plusmn; ' + \
                                     '(?P<skill_error>-?\d+\.\d+)</td><td class=c2>' + \
                                     '(?P<rank>\d+)</td><td class=c>' + \
                                     '(?P<eligible_games_played>\d+)</td><td>' + \
                                     '(?P<nickname>[^<]*) <')

    conn = pymongo.Connection()
    database = conn.test
    history_collection = database.leaderboard_history
    scanner_collection = database.scanner

    db_val = scanner_collection.find_one({'_id': 'leaderboard_history'})
    last_date = db_val['last_date'] if db_val else '0000-00-00'

    directory = 'static/leaderboard/'

    filenames = os.listdir(directory)
    filenames.sort()

    for filename in filenames:
        match = filename_pattern.search(filename)
        if not match:
            continue

        date = match.group('date')

        if '2011-11-24' <= date and date <= '2011-12-04':
            # don't load data from when the leaderboard was messed up
            continue

        if date <= last_date:
            continue

        print date

        file_obj = bz2.BZ2File(directory + filename)
        content = file_obj.read().decode('utf-8')
        file_obj.close()

        nickname_to_entry = {}
        num_matches = 0
        last_rank = -1

        pos = 0
        while True:
            match = leaderboard_pattern.search(content, pos)
            if not match:
                break

            num_matches += 1
            skill_mean = float(match.group('skill_mean'))
            skill_error = float(match.group('skill_error'))
            rank = int(match.group('rank'))
            eligible_games_played = int(match.group('eligible_games_played'))
            nickname = match.group('nickname')

            normed_nickname = name_merger.norm_name(nickname)

            if normed_nickname not in nickname_to_entry:
                nickname_to_entry[normed_nickname] = [date, skill_mean, skill_error, rank, eligible_games_played]
            else:
                print 'normed nickname already exists for this day:', normed_nickname

            last_rank = rank
            pos = match.end()

        print num_matches, 'entries matched'

        if num_matches == 0:
            print 'ERROR: no entries found, so the regex is probably not doing its job anymore.'
            break

        if num_matches != last_rank:
            print 'ERROR: # entries does not match last rank, so the regex is probably not doing its job anymore.'
            break

        for nickname, data in nickname_to_entry.iteritems():
            history_collection.update({'_id': nickname}, {'$push': {'history': data}}, upsert=True)

        print len(nickname_to_entry), 'player histories updated'
        print

        last_date = date

    scanner_collection.update({'_id': 'leaderboard_history'}, {'$set': {'last_date': last_date}}, upsert=True)

if __name__ == '__main__':
    main()

