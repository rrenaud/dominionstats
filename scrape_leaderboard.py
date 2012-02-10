#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
import os
import datetime
import httplib
import StringIO
import gzip
import bz2
import utils

output_directory = 'static/leaderboard/'

def get_date_of_last_cached_leaderboard():
    filename_pattern = re.compile('^(?P<year>\d\d\d\d)-(?P<month>\d\d)-(?P<day>\d\d)\.html\.bz2$')
    filenames = os.listdir(output_directory)
    filenames.sort(reverse=True)

    for filename in filenames:
        match = filename_pattern.search(filename)
        if not match:
            continue
        return datetime.date(int(match.group('year')), int(match.group('month')), int(match.group('day')))

    # return the day before the first day on http://bggdl.square7.ch/leaderboard/
    return datetime.date(2011, 3, 10)

def get_date_of_current_isotropic_leaderboard():
    conn = httplib.HTTPConnection('dominion.isotropic.org')
    conn.request('HEAD', '/leaderboard/')
    res = conn.getresponse()
    headers = dict(res.getheaders())
    conn.close()

    # just after midnight Pacific time, GMT will have the same calendar date as Pacific time
    # so, we can ignore the hour, minute, and second
    return datetime.datetime.strptime(headers['last-modified'], '%a, %d %b %Y %H:%M:%S %Z').date()

def save_file(gzipped_data, date):
    f = gzip.GzipFile(fileobj=StringIO.StringIO(gzipped_data))
    data = f.read()
    f.close()

    data = bz2.compress(data)

    f = open(output_directory + str(date) + '.html.bz2', 'w')
    f.write(data)
    f.close()

def scrape_leaderboard_from_online_cache(date):
    conn = httplib.HTTPConnection('bggdl.square7.ch')
    conn.request('GET', '/leaderboard/leaderboard-' + str(date) + '.html', headers={'Accept-Encoding': 'gzip'})
    res = conn.getresponse()
    gzipped_data = res.read()
    conn.close()

    if res.status == 200:
        save_file(gzipped_data, date)
        return True
    elif res.status == 404:
        # doesn't exist, but pretend we got it
        return True
    else:
        return False

def scrape_leaderboard_from_isotropic(date):
    conn = httplib.HTTPConnection('dominion.isotropic.org')
    conn.request('GET', '/leaderboard/', headers={'Accept-Encoding': 'gzip'})
    res = conn.getresponse()
    gzipped_data = res.read()
    conn.close()

    if res.status == 200:
        save_file(gzipped_data, date)
        return True
    else:
        return False

def main():
    utils.ensure_exists(output_directory)

    one_day_delta = datetime.timedelta(1)
    date = get_date_of_last_cached_leaderboard() + one_day_delta
    date_of_current_isotropic_leaderboard = get_date_of_current_isotropic_leaderboard()
    success = True

    while success and date <= date_of_current_isotropic_leaderboard:
        print date

        if date == date_of_current_isotropic_leaderboard:
            success = scrape_leaderboard_from_isotropic(date)
        else:
            success = scrape_leaderboard_from_online_cache(date)

        date += one_day_delta

if __name__ == '__main__':
    main()

