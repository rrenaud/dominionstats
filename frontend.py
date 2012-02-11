#!/usr/bin/python
# -*- coding: utf-8 -*-
import codecs
import collections
import math
import pprint
import urllib
import urlparse

import pymongo
import simplejson as json
import web

import game
import goals
import query_matcher
from name_merger import norm_name
import annotate_game
import parse_game
from record_summary import RecordSummary
from small_gain_stat import SmallGainStat
import datetime
from optimal_card_ratios import DBCardRatioTracker

import utils
import card_info

urls = (
  '/', 'IndexPage',
  '/player', 'PlayerPage',
  '/player_json', 'PlayerJsonPage',
  '/game', 'GamePage',
  '/search_query', 'SearchQueryPage',
  '/search_result', 'SearchResultPage',
  '/win_rate_diff_accum.html', 'WinRateDiffAccumPage',
  '/win_weighted_accum_turn.html', 'WinWeightedAccumTurnPage',
  '/popular_buys', 'PopularBuyPage',
  '/openings', 'OpeningPage',
  '/goals', 'GoalsPage',
  '/supply_win_api', 'SupplyWinApi',
  '/supply_win', 'SupplyWinPage',
  '/optimal_card_ratios', 'OptimalCardRatios',
  '/(.*)', 'StaticPage'
)

class IndexPage(object):
    def GET(self):
        web.header("Content-Type", "text/html; charset=utf-8")  
        return open('index.html', 'r').read()

class PopularBuyPage(object):
    def GET(self):
        import count_buys
        web.header("Content-Type", "text/html; charset=utf-8")  
        query_dict = dict(urlparse.parse_qsl(web.ctx.env['QUERY_STRING']))

        db = utils.get_mongo_database()
        stats = count_buys.DeckBuyStats()
        utils.read_object_from_db(stats, db.buys, '')
        player_buy_summary = None

        if 'player' in query_dict:
            targ_name = norm_name(query_dict['player'])
            games = map(game.Game, list(db.games.find({'players': targ_name})))
            player_buy_summary = count_buys.DeckBuyStats()
            match_name = lambda g, name: norm_name(name) == targ_name
            count_buys.accum_buy_stats(games, player_buy_summary, match_name)
            count_buys.add_effectiveness(player_buy_summary, stats)

        render = web.template.render('', globals={'round': round})
        return render.buy_template(stats, player_buy_summary)

def make_level_str(floor, ceil):
    if ceil < 0:
        return '-%d' % (-ceil + 1)
    elif floor > 0:
        return '+%d' % (floor + 1)
    else:
        return '0'

def make_level_key(floor, ceil):
    if ceil < 0:
        return -1, ceil
    elif floor > 0:
        return 1, floor
    else:
        return 0, (floor+ceil)/2

def skill_str(mu, sigma):
    return u'%3.3f &plusmn; %3.3f' % (mu, sigma*3)

class OpeningPage(object):
    def GET(self):
        web.header("Content-Type", "text/html; charset=utf-8")  
        query_dict = dict(urlparse.parse_qsl(web.ctx.env['QUERY_STRING']))
        db = utils.get_mongo_database()
        selected_card = ''

        if 'card' in query_dict:
            selected_card = query_dict['card']

        results = db.trueskill_openings.find({'_id': {'$regex': '^open:'}})
        openings = list(results)
        card_list = card_info.OPENING_CARDS
        def split_opening(o):
            ret = o['_id'][len('open:'):].split('+')
            if ret == ['']: return []
            return ret

        if selected_card not in ('All cards', ''):
            openings = [o for o in openings if selected_card in 
                        split_opening(o)]
                        
        openings = [o for o in openings if split_opening(o)]
        for opening in openings:
            floor = opening['mu'] - opening['sigma'] * 3
            ceil = opening['mu'] + opening['sigma'] * 3
            opening['level_key'] = make_level_key(floor, ceil)
            opening['level_str'] = make_level_str(floor, ceil)
            opening['skill_str'] = skill_str(opening['mu'], opening['sigma'])
            opening['cards'] = split_opening(opening)
            opening['cards'].sort()
            opening['cards'].sort(key=lambda card: (card_info.cost(card)),
                reverse=True)
            costs = [str(card_info.cost(card)) for card in opening['cards']]
            while len(costs) < 2:
                costs.append('-')
            opening['cost'] = '/'.join(costs)

        openings.sort(key=lambda opening: opening['level_key'])
        openings.reverse()
        if selected_card == '':
            openings = [op for op in openings
                        if op['level_key'][0] != 0
                        or op['_id'] == ['Silver', 'Silver']]

        render = web.template.render('')
        return render.openings_template(openings, card_list, selected_card)

class PlayerJsonPage(object):
    def GET(self):
        web.header("Content-Type", "text/plain; charset=utf-8")  
        query_dict = dict(urlparse.parse_qsl(web.ctx.env['QUERY_STRING']))
        target_player = query_dict['player']

        db = utils.get_mongo_database()
        games = db.games
        norm_target_player = norm_name(target_player)
        games_coll = games.find({'players': norm_target_player})

        from pymongo import json_util

        games_arr = [{'game': g['decks'], 'id': g['_id']} for g in games_coll]

        return json.dumps(games_arr, default=json_util.default)

def render_record_row(label, rec):
    _row = ('<tr><th>%s</th>' % label,
            '<td>%s</td>' % rec.display_win_loss_tie(),
            '<td>%.3f</td></tr>\n' % rec.average_win_points())
    return ''.join(_row)

def render_record_table(table_name, overall_record,
                        keyed_records, row_label_func):
    #TODO: this is a good target for a template like jinja2
    table = ('<div class="cardborder yellow">',
             '<h3>%s</h3>' % table_name,
             '<table class="stats">',
             '<tr><td></td><th>Record</th><th>Average Win Points</th></tr>\n',
             render_record_row('All games', overall_record),
             ''.join(render_record_row(row_label_func(record_row_cond),
                                       keyed_records[record_row_cond])
                     for record_row_cond in sorted(keyed_records.keys())),
             '</table>',
             '</div>')

    return ''.join(table)

def standard_heading(title):
    return """<html>
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    <title>%s</title>
    <link href='static/css/mystyles.css' rel='stylesheet' type='text/css'>
    <link href='http://fonts.googleapis.com/css?family=IM+Fell+DW+Pica' 
      rel='stylesheet' type='text/css'>
    <link href='http://fonts.googleapis.com/css?family=Terminal+Dosis' rel='stylesheet' type='text/css'>
  </head>
  <body>
    <a href="http://councilroom.com"><h1>CouncilRoom.com</h1></a>""" % title

class PlayerPage(object):
    def GET(self):
        web.header("Content-Type", "text/html; charset=utf-8")  

        query_dict = dict(urlparse.parse_qsl(web.ctx.env['QUERY_STRING']))
        target_player = query_dict['player'].decode('utf-8')

        db = utils.get_mongo_database()
        games = db.games
        norm_target_player = norm_name(target_player)
        games_coll = games.find({'players': norm_target_player})

        leaderboard_history = db.leaderboard_history.find_one({'_id': norm_target_player})
        leaderboard_history = leaderboard_history['history'] if leaderboard_history else None

        keyed_by_opp = collections.defaultdict(list)
        real_name_usage = collections.defaultdict(
            lambda: collections.defaultdict(int))

        game_list = []
        aliases = set()

        overall_record = RecordSummary()
        rec_by_game_size = collections.defaultdict(RecordSummary)
        rec_by_date = collections.defaultdict(RecordSummary)
        rec_by_turn_order =  collections.defaultdict(RecordSummary)

        date_buckets = [1, 3, 5, 10]
        for g in games_coll:
            game_val = game.Game(g)
            if game_val.dubious_quality():
                continue
            all_player_names = game_val.all_player_names()
            norm_names = map(norm_name, all_player_names)
            if len(set(norm_names)) != len(all_player_names):
                continue
            target_player_cur_name_cand = [
                n for n in all_player_names
                if norm_name(n) == norm_target_player]
            if len(target_player_cur_name_cand) != 1:
                continue
            game_list.append(game_val)
            target_player_cur_name = target_player_cur_name_cand[0]
            aliases.add(target_player_cur_name)
            for p in game_val.get_player_decks():
                if p.name() != target_player_cur_name:
                    other_norm_name = norm_name(p.name())
                    keyed_by_opp[other_norm_name].append(
                        (p.name(), target_player_cur_name, game_val))
                    real_name_usage[other_norm_name][p.name()] += 1
                else:
                    res = game_val.win_loss_tie(p.name())
                    overall_record.record_result(res, p.WinPoints())
                    game_len = len(game_val.get_player_decks())
                    rec_by_game_size[game_len].record_result(res,
                                                             p.WinPoints())
                    _ord = p.TurnOrder()
                    rec_by_turn_order[_ord].record_result(res, p.WinPoints())
                    for delta in date_buckets:
                        _padded = (game_val.date() +
                                   datetime.timedelta(days = delta))
                        delta_padded_date = _padded.date()
                        today = datetime.datetime.now().date()
                        if delta_padded_date >= today:
                            rec_by_date[delta].record_result(res,
                                                             p.WinPoints())

        keyed_by_opp_list = keyed_by_opp.items()
        keyed_by_opp_list.sort(key = lambda x: (-len(x[1]), x[0]))
        #TODO: a good choice for a template like jinja2
        ret = standard_heading("CouncilRoom.com: Dominion Stats: %s" % target_player)

        ret += '<form action="/player" method="get">'
        ret += '<span class="subhead">Profile for %s</span>' % target_player

        leaderboard_history_most_recent = leaderboard_history[-1] if leaderboard_history else None
        if leaderboard_history_most_recent:
            level = leaderboard_history_most_recent[1] - leaderboard_history_most_recent[2]
            level = int(max(math.floor(level), 0))
            ret += '<span class="level">Level ' + str(level) + '</span>'

        ret += '<span class="search2">'
        ret += """
               Search for another player:
               <input type="text" name="player" style="width:100px;" />
               <input type="submit" value="View Stats!" />
               </span></form><br><br>
               """

        if len(aliases) > 1:
            ret += 'Aliases: ' + ', '.join(aliases) + '\n'


        ret += render_record_table('Record by game size', overall_record,
                                   rec_by_game_size,
                                   lambda game_size: '%d players' % game_size)
        ret += render_record_table('Recent Record', overall_record,
                                   rec_by_date,
                                   lambda num_days: 'Last %d days' % num_days)
        ret += render_record_table('Record by turn order', overall_record,
                                   rec_by_turn_order,
                                   lambda pos: 'Table position %d' % pos)

        ret += '<div style="clear: both;">&nbsp;</div>'

        ret += goals.MaybeRenderGoals(db, norm_target_player)

        ret += '<A HREF="/popular_buys?player=%s"><h2>Stats by card</h2></A><BR>\n' % target_player

        if leaderboard_history:
            render = web.template.render('')
            ret += str(render.player_page_leaderboard_history_template(json.dumps(leaderboard_history)))

        ret += '<h2>Most recent games</h2>\n'
        game_list.sort(key = game.Game.get_id, reverse = True)
        qm = query_matcher.QueryMatcher(p1_name=target_player)
        for g in game_list[:3]:
            ret += (query_matcher.GameMatcher(g, qm).display_game_snippet() +
                    '<br>')

        ret += ('<A HREF="/search_result?p1_name=%s">(See more)</A>' % 
                target_player)

        ret += '<h2>Record by opponent</h2>'
        ret += '<table border=1>'
        ret += '<tr><td>Opponent</td><td>Record</td></tr>'
        for opp_norm_name, game_list in keyed_by_opp_list:
            record = [0, 0, 0]
            for opp_name, tgt_player_curname, g in game_list:
                record[g.win_loss_tie(tgt_player_curname, opp_name)] += 1
            ret += '<tr>'

            # Get most freq used name for opponent
            #TODO: lambdas can be switched to itemgetters
            opp_cannon_name = max(real_name_usage[opp_norm_name].iteritems(),
                                  key=lambda x: x[1])[0]

            row_span = (len(game_list) - 1) / 10 + 1
            ret += '<td rowspan=%d>%s</td>' % (
                row_span, game.PlayerDeck.PlayerLink(opp_cannon_name))
            ret += '<td rowspan=%d>%d-%d-%d</td>' % (row_span, record[0],
                                                     record[1], record[2])
            for idx, (opp_name, tgt_player_curname, g) in enumerate(
                game_list):
                if idx % 10 == 0 and idx > 0:
                    ret += '</tr><tr>'
                ret += g.short_render_cell_with_perspective(tgt_player_curname,
                                                            opp_name)
            ret += '</tr>\n'
        ret += '</table></body></html>'
        return ret

class GamePage(object):
    def GET(self):
        web.header("Content-Type", "text/html; charset=utf-8")  
        query_dict = dict(urlparse.parse_qsl(web.ctx.env['QUERY_STRING']))
        debug = int(query_dict.get('debug', 0))
        game_id = query_dict['game_id']
        if game_id.endswith('.gz'):
            game_id = game_id[:-len('.gz')]
        yyyymmdd = game.Game.get_date_from_id(game_id)
        contents = codecs.open('static/scrape_data/%s/%s' % (
                yyyymmdd, game_id), 'r', encoding='utf-8').read()
        body_err_msg = ('<body><b>Error annotating game, tell ' 
                        'rrenaud@gmail.com!</b>')
        try:
            return annotate_game.annotate_game(contents, game_id, debug)
        except parse_game.BogusGameError, b:
            return contents.replace('<body>',
                                    body_err_msg + ': foo? ' + str(b))
        except Exception, e:
            import sys, StringIO, traceback
            exc_type, exc_value, exc_traceback = sys.exc_info()
            output = StringIO.StringIO()
            traceback.print_tb(exc_traceback, limit=10, file=output)
            return contents.replace('<body>', body_err_msg + '<br>\n' +
                                    'Exception:'  + str(e) + '<br>' + 
                                    output.getvalue().replace('\n', '<br>').
                                    replace(' ', '&nbsp'))

class SearchQueryPage(object):
    def GET(self):
        web.header("Content-Type", "text/html; charset=utf-8")
        return open('search_query.html', 'r').read()

class SearchResultPage(object):
    def GET(self):
        web.header("Content-Type", "text/html; charset=utf-8")
        query_dict = dict(urlparse.parse_qsl(web.ctx.env['QUERY_STRING']))

        db = utils.get_mongo_database()
        games = db.games

        ret = '<html><head><title>Game Search Results</title></head><body>'

        ret += '<a href="/search_query">Back to search query page</a><BR><BR>'

        matcher = query_matcher.QueryMatcher(**query_dict)
        found_any = False
        for idx, game_match in enumerate(matcher.query_db(games)):
            found_any = True
            ret += game_match.display_game_snippet() + '<br>'
        if not found_any:
            ret += 'Your search returned no matches<br>'

        ret += '<a href="/search_query">Back to search query page</a>'
        return ret

class WinRateDiffAccumPage(object):
    def GET(self):
        render = web.template.render('')
        return render.win_graph_template(
            'Win rate by card accumulation advantage',
            'Difference in number bought/gained on your turn',
            'win_diff_accum',
            'Minion,Gold,Adventurer,Witch,Mountebank',
            'WeightProportionalToAccumDiff'
            )

class WinWeightedAccumTurnPage(object):
    def GET(self):
        render = web.template.render('')
        return render.win_graph_template(
            'Win rate by turn card accumulated',
            'Turn card was gained (only on your turn)',
            'win_weighted_accum_turn',
            'Silver,Cost==3 && Actions>=1 && Cards >= 1',
            'WeightAllTurnsSame'
            )

class GoalsPage(object):
    def GET(self):
        web.header("Content-Type", "text/html; charset=utf-8")
        db = utils.get_mongo_database()
        gstats_db = db.goal_stats
        goal_stats = list(gstats_db.find())

        n = db.games.count()

        ret = standard_heading("CouncilRoom.com: Goal Stats")
        ret += '<span class="subhead">Goal Stats</span>\n<p>\n'
        ret += '<table width="50%">'
        ret += '<tr><td><th>Goal Name<th width="1%">Total Times Achieved<th width="1%">% Occurrence<th>Description<th>Leaders'
        for g in sorted(goal_stats, key=lambda k: k['count'], reverse=True):
            goal_name = g['_id']
            ret += '<tr><td>'
            ret += '<img src="%s" alt="%s"/>' % (goals.GetGoalImageFilename(goal_name), goal_name)
            ret += '<th>%s<td align="right">%d<td align="right">%.2f<td align="center">%s' % (goal_name, g['count'], g['count']*100./n, goals.GetGoalDescription(goal_name))
            rank = 1
            ret += '<td>'
            for (players, count) in g['top']:
                if len(players)==1:
                    ret += "%d) %s (%d)<br />" % (rank, game.PlayerDeck.PlayerLink(players[0]), count)
                else:
                    ret += "%d) %d tied with %d (" % (rank, len(players), count)
                    links = [game.PlayerDeck.PlayerLink(player) for player in players]
                    ret += ', '.join(links)
                    ret += ')<br/>'
                rank += len(players)

        return ret

class SupplyWinApi(object):
    def GET(self):
        web.header("Content-Type", "text/html; charset=utf-8")
        web.header("Access-Control-Allow-Origin", "*")
        query_dict = dict(urlparse.parse_qsl(web.ctx.env['QUERY_STRING']))
        # params:
        # targets, opt
        # cond1, opt
        # cond2, opt
        # format? json, csv?
        db = utils.get_mongo_database()
        targets = query_dict.get('targets', '').split(',')
        if sum(len(t) for t in targets) == 0:
            targets = card_info.card_names()

        # print targets
        def str_card_index(card_name):
            title = card_info.sane_title(card_name)
            if title:
                return str(card_info.card_index(title))
            return ''
        target_inds = map(str_card_index, targets)
        # print targets, target_inds

        cond1 = str_card_index(query_dict.get('cond1', ''))
        cond2 = str_card_index(query_dict.get('cond2', ''))
        
        if cond1 < cond2:
            cond1, cond2 = cond2, cond1

        card_stats = {}
        for target_ind in target_inds:
            key = target_ind + ';'
            if cond1:
                key += cond1
            if cond2:
                key += ',' + cond2

            db_val = db.card_supply.find_one({'_id': key})
            if db_val:
                small_gain_stat = SmallGainStat()
                small_gain_stat.from_primitive_object(db_val['vals'])
                card_name = card_info.card_names()[int(target_ind)]
                card_stats[card_name] = small_gain_stat
        
        format = query_dict.get('format', 'json')
        if format == 'json':
            readable_card_stats = {}
            for card_name, card_stat in card_stats.iteritems():
                readable_card_stats[card_name] = (
                    card_stat.to_readable_primitive_object())
            return json.dumps(readable_card_stats)
        return 'unsupported format ' + format

class SupplyWinPage(object):
    def GET(self):
        return open('supply_win.html').read()

class OptimalCardRatios(object):
    def GET(self):
        web.header("Content-Type", "text/html; charset=utf-8")
        query_dict = dict(urlparse.parse_qsl(web.ctx.env['QUERY_STRING']))

        card_list = sorted(set(card_info.card_names()) - set(card_info.TOURNAMENT_WINNINGS))

        if query_dict.has_key('card_x'):
            card_x = query_dict['card_x']
        else:
            card_x = 'Minion'
        if query_dict.has_key('card_y'):
            card_y = query_dict['card_y']
        else:
            card_y = 'Gold'

        if card_x < card_y:
            db_id = card_x + ':' + card_y
            swap_x_and_y = False
        else:
            db_id = card_y + ':' + card_x
            swap_x_and_y = True

        db = utils.get_mongo_database()
        db_val = db.optimal_card_ratios.find_one({'_id': db_id})

        if not db_val:
            return 'No stats for "' + card_x + '" and "' + card_y + '".'

        tracker = DBCardRatioTracker()
        tracker.from_primitive_object(db_val)

        num_games = sum(meanvarstat.frequency() for meanvarstat in tracker.final.itervalues())
        num_games_threshold = int(round(num_games * .002))
        final_table = self.getHtmlTableForStats(tracker.final, swap_x_and_y, num_games, num_games_threshold)

        num_games = max(meanvarstat.frequency() for meanvarstat in tracker.progressive.itervalues())
        num_games_threshold = int(round(num_games * .002))
        progressive_table = self.getHtmlTableForStats(tracker.progressive, swap_x_and_y, num_games, num_games_threshold)

        render = web.template.render('')
        return render.optimal_card_ratios_template(card_list, card_x, card_y, final_table, progressive_table)

    @staticmethod
    def getHtmlTableForStats(stats, swap_x_and_y, num_games, num_games_threshold):
        x_to_y_to_data = {}
        min_x = 1e6
        max_x = -1e6
        min_y = 1e6
        max_y = -1e6
        min_mean = 1e6
        max_mean = -1e6

        for key, meanvarstat in stats.iteritems():
            if meanvarstat.frequency() < num_games_threshold:
                continue

            x, y = key.split(':')
            x, y = int(x), int(y)
            if swap_x_and_y:
                x, y = y, x
            mean = meanvarstat.mean()

            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)
            min_mean = min(min_mean, mean)
            max_mean = max(max_mean, mean)

            if not x_to_y_to_data.has_key(x):
                x_to_y_to_data[x] = {}
            x_to_y_to_data[x][y] = (mean, meanvarstat.render_interval(), meanvarstat.frequency())

        # clamp to 0, for now
        min_x = 0
        min_y = 0

        render = web.template.render('', globals={'get_background_color': OptimalCardRatios.getBackgroundColor})
        return render.optimal_card_ratios_table_template(min_x, max_x, min_y, max_y, min_mean, max_mean, x_to_y_to_data, num_games, num_games_threshold)

    @staticmethod
    def getBackgroundColor(min_mean, max_mean, value):
        background_colors = [
            [min_mean, [255, 0, 0]],
            [(max_mean + min_mean) / 2, [255, 255, 0]],
            [max_mean, [0, 255, 0]],
        ]
        for index in xrange(1, len(background_colors)):
            if value <= background_colors[index][0]:
                break
        value_min, color_min = background_colors[index-1]
        value_max, color_max = background_colors[index]
        color = '#'
        amount = (value - value_min) / (value_max - value_min)
        for x in xrange(3):
            component = int(color_min[x] + amount * (color_max[x] - color_min[x]))
            component = max(0, component)
            component = min(component, 255)
            color += '{0:02x}'.format(component)
        return color

class StaticPage(object):
    def GET(self, arg):
        import os.path
        if os.path.exists(arg):
            return open(arg, 'r').read()
        else:
            raise web.notfound()

def notfound():
    return web.notfound( "This page is not found.  Blame it on rrenaud." )

application = web.application(urls, globals())

application.notfound = notfound
