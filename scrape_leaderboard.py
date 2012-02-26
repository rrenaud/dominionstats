#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
import os
import datetime
import httplib
import socket
import StringIO
import gzip
import bz2
import utils

output_directory = 'static/leaderboard/'

def date_from_http_header_time(http_header_time):
    return datetime.datetime.strptime(http_header_time, '%a, %d %b %Y %H:%M:%S %Z').date()

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
    try:
        connection = httplib.HTTPConnection('dominion.isotropic.org', timeout=30)
        connection.request('HEAD', '/leaderboard/')
        response = connection.getresponse()
        headers = dict(response.getheaders())
        connection.close()
    except socket.error:
        return

    if response.status == 200:
        # just after midnight Pacific time, GMT will have the same calendar date as Pacific time
        # so, we can ignore the hour, minute, and second
        return date_from_http_header_time(headers['last-modified'])

def save_file(date, data, is_gzipped):
    if is_gzipped:
        f = gzip.GzipFile(fileobj=StringIO.StringIO(data))
        data = f.read()
        f.close()

        data = bz2.compress(data)

    f = open(output_directory + str(date) + '.html.bz2', 'w')
    f.write(data)
    f.close()

def scrape_leaderboard(date, host, url, is_gzipped, assert_same_date):
    try:
        connection = httplib.HTTPConnection(host, timeout=30)
        connection.request('GET', url, headers={'Accept-Encoding': 'gzip'} if is_gzipped else {})
        response = connection.getresponse()
        data = response.read()
        connection.close()
    except socket.error:
        return 'socket error'

    if assert_same_date:
        headers = dict(response.getheaders())
        if date != date_from_http_header_time(headers['last-modified']):
            return 'leaderboard updated'

    if response.status == 200:
        save_file(date, data, is_gzipped)

    return response.status

def scrape_leaderboard_from_isotropic(date):
    return scrape_leaderboard(date, 'dominion.isotropic.org', '/leaderboard/', True, True)

def scrape_leaderboard_from_councilroom(date):
    return scrape_leaderboard(date, 'councilroom.com', '/static/leaderboard/' + str(date) + '.html.bz2', False, False)

def scrape_leaderboard_from_bggdl(date):
    return scrape_leaderboard(date, 'bggdl.square7.ch', '/leaderboard/leaderboard-' + str(date) + '.html', True, False)

def run_scrape_function_with_retries(scrape_function, date):
    num_attempts = 0

    while True:
        num_attempts += 1

        status = scrape_function(date)

        if status == 200:
            print 'successful'
            break
        elif status == 404:
            print 'file not found'
            break
        elif status == 'leaderboard updated':
            print 'the leaderboard was updated after this script was started, so re-run this script'
            break
        else:
            if num_attempts < 3:
                print 'retrying'
            else:
                print 'reached 3 attempts, aborting'
                break

    return status

def main():
    utils.ensure_exists(output_directory)

    date_of_last_cached_leaderboard = get_date_of_last_cached_leaderboard()
    print 'date of the last cached leaderboard is', date_of_last_cached_leaderboard

    date_of_current_isotropic_leaderboard = get_date_of_current_isotropic_leaderboard()
    if date_of_current_isotropic_leaderboard is None:
        print 'could not determine the date of the current isotropic leaderboard, so please try again later'
        return
    print 'date of the current isotropic leaderboard is', date_of_current_isotropic_leaderboard

    one_day_delta = datetime.timedelta(1)
    date = date_of_last_cached_leaderboard + one_day_delta

    while date <= date_of_current_isotropic_leaderboard:
        print
        print date

        if date == date_of_current_isotropic_leaderboard:
            print 'scraping from isotropic'
            status = run_scrape_function_with_retries(scrape_leaderboard_from_isotropic, date)
        else:
            print 'scraping from councilroom'
            status = run_scrape_function_with_retries(scrape_leaderboard_from_councilroom, date)

            if status != 200:
                print 'scraping from bggdl'
                status = run_scrape_function_with_retries(scrape_leaderboard_from_bggdl, date)

        if status == 200:
            pass
        elif status == 404:
            print 'file not found, so we will assume that it does not exist, and go to the next day'
        else:
            print 'please try again later'
            break

        date += one_day_delta

if __name__ == '__main__':
    main()

