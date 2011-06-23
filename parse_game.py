#!/usr/bin/python
# -*- coding: utf-8 -*-

"""Parse raw game data from isotropic into JSON list of game documents."""

import collections
import codecs
import os
import multiprocessing
import pprint
import re
import sys

import card_info
import game
import utils
import name_merger
from game import Game

import simplejson as json

SECTION_SEP = re.compile('^----------------------$', re.MULTILINE)

NORM_TURN_HEADER_RE = re.compile(
    "--- (?P<name>.+)'s turn (?P<turn_no>\d+) ---")
POSS_TURN_HEADER_RE = re.compile(
    "--- (?P<name>.+)'s turn \(possessed by (?P<pname>.*)\) ---")
OUTPOST_TURN_HEADER_RE = re.compile(
    "--- (?P<name>.+)'s " + re.escape(
        "extra turn (from <span class=card-duration>Outpost</span>)"))
            
TURN_HEADER_NO_GROUP_RE = re.compile("--- .+'s turn [^-]* ---")
SPLIT_COMMA_AND_RE = re.compile(',| and ')
NUMBER_BEFORE_SPAN = re.compile('(\d+) <span')
NUMBER_COPIES = re.compile('(0|2) copies to')
GETTING_MONEY_RE = re.compile(' \+\$(\d)+')
WHICH_IS_WORTH_RE = re.compile(' which is worth \+\$(\d)+')
VP_TOKEN_RE = re.compile(u'(?P<num>\d+) ▼', re.UNICODE)

KW_ANOTHER_ONE = 'another one'
KW_BUYS = ' buys '
KW_DISCARDS = ' discards '
KW_GAINING = ' gaining ' 
KW_GAINS_A = ' gains a'
KW_GAINS_THE = ' gains the '
KW_GETS = ' gets +'
KW_GETTING = ' getting +'
KW_IS_TRASHED = ' is trashed.'
KW_PLAYING = ' playing '
KW_PLAYS = ' plays ' 
KW_REPLACING = ' replacing '
KW_RETURNING = ' returning ' 
KW_REVEALING = ' revealing '
KW_REVEALS = ' reveals '
KW_REVEALS_A = ' reveals a'
KW_TOKEN = ' token.'
KW_TO_THE_SUPPLY = ' to the supply'
KW_TRASHES = ' trashes ' 
KW_TRASHES_IT = 'trashes it.'
KW_TRASHING = ' trashing '
KW_TURNS_UP_A = ' turns up a'
KW_WHICH_IS_WORTH = ' which is worth +$'
KW_WITH_A = ' with a'
KEYWORDS = [locals()[w] for w in dict(locals()) if w.startswith('KW_')]

class BogusGameError(Exception):
    """ Exception for a degenerate game that cannot or should not be parsed."""

    def __init__(self, reason):
        Exception.__init__(self)
        self.reason = reason

def capture_cards(line):
    """ Given a line of text from isotropic, extract the card names.

    line: string like 'Rob plays a <span class=card-none>Minion</span>.'
    returns: list of string of card names, eg, ['Minion']
    """
    def _as_int_or_1(string_val):
        try:
            return int(string_val)
        except ValueError:
            return 1

    cards = []
    card_sections = SPLIT_COMMA_AND_RE.split(line)
    for sect in card_sections:
        split_at_span = sect.split('<span')
        if not split_at_span:
            continue
        first = split_at_span[0]
        split_first = first.split()
        if not split_first:
            mult = 1
        else:
            mult = _as_int_or_1(split_first[-1])

        for subsect in split_at_span:
            start_of_end_span = subsect.find('</span')
            if start_of_end_span == -1:
                continue
            end_of_begin_span = subsect.rfind('>', 0, start_of_end_span)
            if end_of_begin_span == -1:
                continue
            maybe_plural = subsect[end_of_begin_span + 1: 
                                   start_of_end_span]
            if maybe_plural == '&diams;':
                continue
            try:
                card = card_info.singular_of(maybe_plural)
            except KeyError, exception:
                print line
                raise exception
            cards.extend([card] * mult)
    return cards    

def assign_win_points(game_dict):
    """ Set win_points to number of win points for each player in game_dict."""
    def win_tuple(deck_dict):        
        """ Return tuple ordered by increasing final standing. """
        # negate turns so that max() behaves; points good, turns bad.
        num_normal_turns = sum(not ('poss' in t or 'outpost' in t) 
                               for t in deck_dict['turns'])
        return (deck_dict['points'], -num_normal_turns)

    decks = game_dict['decks']
    winner_tuple = max(win_tuple(p) for p in decks)
    winners = [p for p in decks if win_tuple(p) == winner_tuple]

    win_points = float(len(decks)) / len(winners)
    for player in decks:
        player['win_points'] = win_points if player in winners else 0.0

def _player_label(ind):
    return 'player' + str(ind)

def associate_game_with_norm_names(game_dict):
    """ Fill players field in game_dict with list of normed player names."""
    game_dict['players'] = []
    for player_deck in game_dict['decks']:
        normed_name = name_merger.norm_name(player_deck['name'])
        game_dict['players'].append(normed_name)

def associate_turns_with_owner(game_dict, turns):
    """ Move each turn in turns to be a member of the corresponding player
    in game_dict.  

    Remove the names from the turn, since it is redundant with the name
    on the player level dict."""
    name_to_owner = {}
    for idx, deck in enumerate(game_dict['decks']):
        name_to_owner[deck['name']] = deck
        deck['turns'] = []

    order_ct = 0

    for idx, turn in enumerate(turns):
        owner = name_to_owner[turn['name']]
        owner['turns'].append(turn)
        if not 'order' in owner:
            owner['order'] = idx + 1
            order_ct += 1
        del turn['name']

    if order_ct != len(game_dict['decks']):
        raise BogusGameError('Did not find turns for all players')

ONLY_NUMBERS_RE = re.compile('^\d+$')

def validate_names(decks):
    """ Raise an exception for names that might screw up the parsing.  
    This should happen in less than 1% of real games, but it's just easier 
    to punt on annoying inputs that to make sure we get them right."""
    used_names = set()
    for deck in decks:
        name = deck['name']
        if name in used_names:
            raise BogusGameError('Duplicate name %s' % name)
        used_names.add(name)

        if name in ['a', 'and']:
            raise BogusGameError("annoying name " + name)
        if '---' in name:
            raise BogusGameError('--- in name ' + name)
        
        if ONLY_NUMBERS_RE.match(name):
            raise BogusGameError('name contains only numbers ' + name)

        if name[0] == '.':
            raise BogusGameError('name %s starts with period' % name)
        for kword in KEYWORDS:
            if kword.lstrip() in name or kword.rstrip() in name:
                raise BogusGameError('name %s contains keyword %s' % (name, kword))

    if len(used_names) != len(decks):
        raise BogusGameError('not everyone took a turn?')
    if len(decks) <= 1:
        raise BogusGameError('only one player')

def canonicalize_names(turns_str, player_names):
    """ Return a new string in which all player names are replaced by
    player0, player1, ..."""
    player_ind_name_pairs = list(enumerate(player_names))
    # Replace longer names first, short names might contain the longer ones.
    player_ind_name_pairs.sort(key = lambda ind_name_pair: 
                               -len(ind_name_pair[1]))
    for idx, player in player_ind_name_pairs:
        # This is complicated (matching extra stuff to the left and right
        # of name rather than straight string replace) so that we 
        # can allow for annoying names like 'd' that occur as
        # substrings of regular text.
        match_player_name = re.compile(
            '(^|[ \(])' +       # start with newline, space, or open paren
            re.escape(player) + # followed by player name
            "([ '\)])",         # ending with space or ' or close paren
            re.MULTILINE)
        def _replace_name_by_label(match):
            """ keep surrounding delims, replace player name with playerX"""
            return match.group(1) + _player_label(idx) + match.group(2)
        turns_str = match_player_name.sub(_replace_name_by_label, turns_str)

    return turns_str

def parse_game(game_str, dubious_check = False):
    """ Parse game_str into game dictionary

    game_str: Entire contents of an isotropic log file.
    dubious_check: If true, raise a BogusGame exception if the game is
      suspicious.

    returns a dict with the following fields:
      decks: A list of player decks, as documend in parse_deck().
      supply: A list of cards in the supply.
      players: A list of normalized player names.
      game_end: List of cards exhausted that caused the game to end.
      resigned: True iff some player in the game resigned..
    """
    game_str = game_str.replace('&mdash;', '---')
    try:
        split_sects = SECTION_SEP.split(game_str)
        header_str, decks_blob, trash_and_turns = split_sects
    except ValueError, exception:
        print len(split_sects), SECTION_SEP.split(game_str), game_str
        raise exception
    game_dict = parse_header(header_str)
    decks = parse_decks(decks_blob)
    game_dict['decks'] = decks
    validate_names(decks)

    names_list = [d['name'] for d in game_dict['decks']]
    turns_str = trash_and_turns.split('Game log')[1]
    turns_str = turns_str[turns_str.find('---'):]
    turns_str = canonicalize_names(turns_str, names_list)
    
    turns = parse_turns(turns_str, names_list)
    
    associate_game_with_norm_names(game_dict)
    associate_turns_with_owner(game_dict, turns)
    assign_win_points(game_dict)

    if dubious_check and Game(game_dict).dubious_quality():
        raise BogusGameError('Dubious Quality')

    return game_dict

def parse_header(header_str):
    """ Parse the header string.

    Return a dictionary with game_end, supply, and resigned fields, 
      like parse_game.
    """
    sections = [s for s in header_str.replace(' \n', '\n').split('\n\n') if s]
    end_str, supply_str = sections
    assert 'gone' in end_str or 'resigned' in end_str
    if 'gone' in end_str:
        resigned = False
        gone = capture_cards(end_str.split('\n')[1])
    else:
        resigned = True
        gone = []
    supply = capture_cards(supply_str)
    return {'game_end': gone, 'supply': supply, 'resigned': resigned}

PLACEMENT_RE = re.compile('#\d (.*)')
POINTS_RE = re.compile(': (-*\d+) points(\s|(' + re.escape('</b>') + '))')

def parse_deck(deck_str):
    """ Given an isotropic deck string, return a dictionary containing the
    player names
    
    deck_str: starts with placement and name, ends with last card in deck.
    returns dictionary containing the following fields
      name: 
      vp_tokens: number of vp tokens.
      deck: Dictionary keyed card name who value is the card frequency.
      resigned: True iff this player resigned
      """
    try:
        name_vp_list, _opening, deck_contents = deck_str.split('\n')
    except ValueError, e:
        print deck_str
        raise e
    vp_tokens = 0
    #print 'vp', name_vp_list

    matched_points = POINTS_RE.search(name_vp_list)
    
    if matched_points:
        point_loc = matched_points.end()
        resigned, points  = False, int(matched_points.group(1))
        name_points, vp_list = (name_vp_list[:point_loc], 
                                name_vp_list[point_loc + 1:])
    else:
        resign_loc = name_vp_list.find('resigned')
        assert resign_loc != -1
        resigned, points = True, -100
        name_points, vp_list = (name_vp_list[:resign_loc],
                                name_vp_list[resign_loc + 1:])

    last_colon_in_name_points = name_points.rfind(':')
    name, _points_or_resign = (name_points[:last_colon_in_name_points],
                               name_points[last_colon_in_name_points + 1:])

    def cleanup_name(name):
        """ Given a name and placement, get rid of the bold tags and  """
        htmlless_name = name.replace('<b>', '').replace('</b>', '')
        placement_match = PLACEMENT_RE.match(htmlless_name)
        if placement_match:
            return placement_match.group(1)
        return htmlless_name

    name = cleanup_name(name)

    for chunk in vp_list.split(','):
        diamond_loc = chunk.find(u'▼')
        if diamond_loc != -1:
            start_point_loc = max(chunk.rfind('(', 0, diamond_loc - 1),
                                  chunk.rfind(' ', 0, diamond_loc - 1))
            vp_tokens = int(chunk[start_point_loc + 1:diamond_loc - 1])

        card_list_chunks = deck_contents[
            deck_contents.find(']') + 1:].replace(',', ' ')
        card_blobs = [x for x in card_list_chunks.split('</span>') if 
                      '<span' in x]
        deck_comp = {}
        for card_blob in card_blobs:
            right_bracket_index = card_blob.find('>')
            card_name = card_blob[right_bracket_index + 1:]
            try:
                card_name = card_info.singular_of(card_name)
            except KeyError, exception:
                print chunk, card_name, card_blob[right_bracket_index - 10:]
                raise exception
            card_quant = int(card_blob.split()[0])
            deck_comp[card_name] = card_quant
    #FIXME: deck_comp is undefined if there's no vp_list
    return {'name': name, 'points': points, 'resigned': resigned,
            'deck': deck_comp, 'vp_tokens': vp_tokens}

def parse_decks(decks_blob):
    """ Parse and return a list of decks"""
    deck_blobs = [s for s in decks_blob.split('\n\n') if s]
    return [parse_deck(deck_blob) for deck_blob in deck_blobs]

def name_and_rest(line, term):
    """ Split line about term, return (before, after including term). """
    start_of_term = line.find(term)
    assert start_of_term != -1

    def _strip_leading(val, dead_chars):
        for idx, char in enumerate(val):
            if char not in dead_chars:
                return val[idx:]
        return ''

    name = _strip_leading(line[:start_of_term], ' .').strip()
    return name, line[start_of_term + len(term):]

def delete_keys_with_empty_vals(dict_obj):
    """ Remove keys from object associated with values that are False/empty."""
    keys_to_die = []
    for k in dict_obj.keys():
        if isinstance(dict_obj[k], dict):
            delete_keys_with_empty_vals(dict_obj[k])
        if not dict_obj[k]:
            keys_to_die.append(k)
    for k in keys_to_die:
        del dict_obj[k]

def count_money(plays):
    """ Return the value of the money from playing cards in plays.

    This does not include money from cards like Steward or Bank, but does
    count Copper. 

    plays: list of cards.
    """
    coppersmith_ct = 0
    money = 0
    for card in plays:
        if card == 'Coppersmith':  
            coppersmith_ct += 1
        elif card == 'Copper':
            money += 1 + coppersmith_ct
        elif card_info.is_treasure(card):
            money += card_info.money_value(card)
    return money

PLAYER_IND_RE = re.compile('player(?P<num>\d+)')

class PlayerTracker(object):
    ''' The player tracker is used to keep track of the active player being
    modified by the gain and trashes actions in a sequence of isotropic
    game lines. '''

    def __init__(self):
        self.player_stack = [None]
        self.orig_player = None

    def get_active_player(self, line):
        ''' Feed the next line to the tracker, it returns the active player.'''
        mentioned_players = self._get_player_inds(line)

        indent_level = line.count('...')
        if indent_level >= len(self.player_stack):
            self.player_stack.append(self.player_stack[-1])
        while len(self.player_stack) > indent_level + 1:
            self.player_stack.pop()

        if len(mentioned_players) > 0:
            self.player_stack[-1] = mentioned_players[-1]
            if self.orig_player is None:
                self.orig_player = mentioned_players[-1]

        return self.player_stack[-1]

    def current_player(self):
        ''' Return the player whose turn it is.
        This requires at least one call to get_active_player() first. '''
        return self.orig_player

    def _get_player_inds(self, line):
        '''return list of player indicies in given line.
        eg, line "player1 trashes player2's ..." -> [1, 2]
        '''
        return map(int, PLAYER_IND_RE.findall(line))

def _get_real_name(canon_name, names_list):
    return names_list[int(PLAYER_IND_RE.match(canon_name).group('num'))]

class ParseTurnHeaderError(Exception):
    def __init__(self, line):
        self.line = line

    def __str__(self):
        return repr(self)
        
    def __repr__(self):
        return 'ParseTurnHeaderError %s' % self.line

def parse_turn_header(turn_header_line, names_list = None):
    """ Given a turn header line return a dictionary containing 
    information about the turn.  All turns have a player name in the key 
    'name'.

    Normal turns have a 'turn_no'.
    Possession turns have a 'pname' for the name of the possessor.
    Outpost turns have the 'outpost' value set to true."""

    # This could be done with a single really complicated regexp, but I kept
    # screwing up the regexp when I tried to join them, and so here we 
    # have some code to match against the three different cases.

    def _get_name(match, name_key = 'name'):
        if names_list is None:
            return match.group(name_key)
        return _get_real_name(match.group(name_key), names_list)

    parsed_header = {}
    norm_match = NORM_TURN_HEADER_RE.search(turn_header_line)
    if norm_match:
        parsed_header['turn_no'] = int(norm_match.group('turn_no'))
        parsed_header['name'] = _get_name(norm_match)
        return parsed_header

    poss_match = POSS_TURN_HEADER_RE.search(turn_header_line)
    if poss_match:
        parsed_header['name'] = _get_name(poss_match)
        parsed_header['pname'] = _get_name(poss_match, 'pname')
        return parsed_header

    out_match = OUTPOST_TURN_HEADER_RE.search(turn_header_line)
    if out_match:
        parsed_header['name'] = _get_name(out_match)
        parsed_header['outpost'] = True
        return parsed_header

    raise ParseTurnHeaderError(turn_header_line)

def parse_turn(turn_blob, names_list):
    """ Parse the information from a given turn.

    Return a dict containing the following fields.  If any of the fields have
    a value that evaluates to False, do not keep it.
    
    name: player name.
    number: 1 indexed turn number.
    plays: List of cards played.
    buys: List of cards bought.
    gains: List of cards gained.
    trashes: List of cards trashed.
    returns: List of cards returned.
    ps_tokens: Number of pirate ship tokens gained.
    vp_tokens: Number of victory point tokens gained.
    money: Amount of money available during entire buy phase.
    opp: Dict keyed by opponent name, containing dicts with trashes/gains.
    """
    lines = turn_blob.strip().split('\n')
    header = lines[0]
    parsed_header = parse_turn_header(header, names_list)
    
    poss, outpost = False, False

    if 'pname' in parsed_header:
        possessee_name = parsed_header['name']
        poss = True
    if 'outpost' in parsed_header:
        outpost = True

    ret = {'gains': [], 'trashes': []}
    plays = []
    buys = []
    returns = []
    turn_money = 0
    vp_tokens = 0
    ps_tokens = 0
    opp_turn_info = collections.defaultdict(lambda: {'gains': [],
                                                     'trashes': []})
    tracker = PlayerTracker()
    for line_idx, line in enumerate(lines):
        active_player = tracker.get_active_player(line)
        if active_player == tracker.current_player():
            targ_obj = ret
        else:
            targ_obj = opp_turn_info[names_list[active_player]]

        has_trashing = KW_TRASHING in line
        has_trashes = KW_TRASHES in line
        has_gaining = KW_GAINING in line

        if has_trashes:
            if has_gaining:
                # Trading post turn, first trashes, then gaining
                gain_start = line.find(KW_GAINING)
                targ_obj['trashes'].extend(capture_cards(line[:gain_start]))
                targ_obj['gains'].extend(capture_cards(line[gain_start:]))
                continue
            targ_obj['trashes'].extend(capture_cards(line))
        if KW_WITH_A in line:
            if KW_REPLACING in line:
                new_gained_portion = line[line.find(KW_WITH_A):]
                targ_obj['gains'].extend(capture_cards(new_gained_portion))
        if KW_PLAYS in line or KW_PLAYING in line: 
            plays.extend(capture_cards(line))
        if has_gaining:
            if KW_ANOTHER_ONE in line: # mints a gold gaining another one
                targ_obj['gains'].extend(capture_cards(line))
            else:
                # gaining always associated with current player?
                targ_obj['gains'].extend( 
                    capture_cards(line[line.find(KW_GAINING):])) 
        if KW_BUYS in line: 
            buys.extend(capture_cards(line))
        if KW_GAINS_THE in line:
            targ_obj['gains'].extend(capture_cards(line))
        if has_trashing: 
            if KW_REVEALING in line:  # reveals watchtower trashing ...
                trashed = capture_cards(line[line.find(KW_TRASHING):])
                targ_obj['trashes'].extend(trashed)
            else:
                rest = line
                if KW_GAINING in line:
                    rest = line[:line.find(KW_GAINING)]
                targ_obj['trashes'].extend(capture_cards(rest))
        if KW_GAINS_A in line:
            if KW_TOKEN in line:
                assert 'Pirate Ship' in capture_cards(line)
                ps_tokens += 1
            else:
                rest = line[line.find(KW_GAINS_A):]
                targ_obj['gains'].extend(capture_cards(rest))
        if KW_IS_TRASHED in line:
            # Saboteur after revealing cards, name not mentioned on this line.
            cards = capture_cards(line)
            targ_obj['trashes'].extend(cards)
        if KW_REVEALS in line:
            card_revealed = capture_cards(line)

            # arg, ambassador requires looking at the next line to figure
            # out how many copies were returned
            if (card_revealed and line_idx + 1 < len(lines) and 
                KW_RETURNING in lines[line_idx + 1] and not
                KW_REVEALING in lines[line_idx + 1]):
                next_line = lines[line_idx + 1]
                num_copies = 1
                num_copies_match = NUMBER_COPIES.search(next_line)
                if num_copies_match:
                    num_copies = int(num_copies_match.group(1))
                returns.extend(card_revealed * num_copies)
        if KW_REVEALING in line and KW_TO_THE_SUPPLY in line:
            # old style ambassador line
            returns.extend(capture_cards(line))
        if KW_GETTING in line or KW_GETS in line:
            money_match = GETTING_MONEY_RE.search(line)
            if money_match:
                turn_money += int(money_match.group(1))
        if KW_WHICH_IS_WORTH in line:
            worth_match = WHICH_IS_WORTH_RE.search(line)
            assert bool(worth_match), line
            turn_money += int(worth_match.group(1))
        if u'▼' in line:
            vp_tokens += int(VP_TOKEN_RE.search(line).group('num'))
            
    if poss:
        def _delete_if_exists(d, n):
            if n in d:
                del d[n]

        possessee_info = opp_turn_info[possessee_name]
        for k in ['gains', 'trashes']:
            _delete_if_exists(possessee_info, k)

        possessee_info['vp_token'], vp_tokens = vp_tokens, 0
        possessee_info['returns'], returns = returns, []
        buys = []  # buys handled by possesion gain line.

    for opp in opp_turn_info.keys():
        delete_keys_with_empty_vals(opp_turn_info[opp])
    ret.update({'name': names_list[tracker.current_player()], 
                'plays': plays , 'buys': buys, 'returns': returns,
                'money': count_money(plays) + turn_money,
                'vp_tokens': vp_tokens, 'ps_tokens': ps_tokens,
                'poss': poss, 'outpost': outpost, 
                'opp': dict(opp_turn_info)})

    delete_keys_with_empty_vals(ret)
    return ret

def split_turns(turns_blob):
    """ Given a string of game play data, return a list of turn strings
    separated by turn headers."""
    turn_texts = ['']
    for line in turns_blob.split('\n'):
        try:
            parse_turn_header(line)
            turn_texts.append(line + '\n')
        except ParseTurnHeaderError, e:
            turn_texts[-1] += line + '\n'
    return [t for t in turn_texts if t]

def parse_turns(turns_blob, names_list):
    """ Return a list of turn objects, as documented by parse_turn(). """
    return [parse_turn(text, names_list) for text in split_turns(turns_blob)]

def outer_parse_game(filename):
    """ Parse game from filename. """
    contents = codecs.open(filename, 'r', encoding='utf-8').read()

    if not contents:
        # print 'empty game'
        return None
    if '<b>game aborted' in contents:
        # print 'skipping aborted game', filename
        return None
    try:
        parsed = parse_game(contents, dubious_check = True)
        parsed['_id'] = filename.split('/')[-1]
        return parsed
    except BogusGameError, bogus_game_exception:
        # print 'skipped', filename, 'because', bogus_game_exception.reason
        return None
    except ParseTurnHeaderError, p:
        print 'parse turn header error', p

# http://stackoverflow.com/questions/312443/how-do-you-split-a-list-into-evenly-sized-chunks-in-python
def segments(lis, chunk_size):
    """ Return an iterator over sublists whose size matches chunk_size. """
    for i in xrange(0, len(lis), chunk_size):
        yield lis[i:i + chunk_size]

def dump_segment(arg_tuple):
    """ Write a json serialized version of games to to name determined by 
    arg tuple.  arg_tuple is in this annoying format for compatibility with 
    multiprocessing.pool.map.
    """
    idx, year_month_day, segment = arg_tuple
    out_name = 'parsed_out/%s-%d.json' % (year_month_day, idx)
    json.dump(segment, open(out_name, 'w'), indent=2, sort_keys=True)

def convert_to_json(year_month_day, games_to_parse = None):
    """ Parse the games in for given year_month_day and output them
    into split local files.  Each local file should contain 100 games or
    less, and be smaller than 4 MB, for easy import into mongodb.

    year_month_day: string in yyyymmdd format encoding date
    games_to_parse: if given, use these games rather than all files in dir.
    """
    if games_to_parse is None:
        games_to_parse = os.listdir('static/scrape_data/' + year_month_day)
        games_to_parse = ['static/scrape_data/' + year_month_day + '/' + g 
                          for g in games_to_parse if g.endswith('html')]

    if not games_to_parse:
        print 'no data files to parse in ', year_month_day
        return
    else:
        print len(games_to_parse), 'games to parse in', year_month_day

    # games_to_parse = games_to_parse[:10]
    pool = multiprocessing.Pool()
    parsed_games = pool.map(outer_parse_game, games_to_parse, chunksize=50)

    #parsed_games = map(outer_parse_game, games_to_parse)
    print year_month_day, 'before filtering', len(parsed_games)
    parsed_games = [x for x in parsed_games if x]

    track_brokenness(parsed_games)

    print year_month_day, 'after filtering', len(parsed_games)
    game_segments = list(segments(parsed_games, 100))
    labelled_segments = [(i, year_month_day, c) for i, c in
                         enumerate(game_segments)]
    pool.map(dump_segment, labelled_segments)
    #map(dump_segment, labelled_segments)
    pool.close()

def track_brokenness(parsed_games):
    """Print some summary statistics about cards that cause bad parses."""
    wrongness = collections.defaultdict(int)
    overall = collections.defaultdict(int)
    for raw_game in parsed_games:
        accurately_parsed = check_game_sanity(game.Game(raw_game), sys.stdout)
        #if not accurately_parsed:
        #    print raw_game['_id']
        for card in raw_game['supply']:
            if not accurately_parsed:
                wrongness[card] += 1
            overall[card] += 1

    ratios = []
    for card in overall:
        ratios.append(((float(wrongness[card]) / overall[card]), card))
    ratios.sort()
    if ratios[-1][0] > 0:
        print ratios[-10:]
    else:
        print 'perfect parsing!'

def parse_game_from_file(filename):
    """ Return a parsed version of a given filename. """
    contents = codecs.open(filename, 'r', encoding='utf-8').read()
    return parse_game(contents, dubious_check = True)

def check_game_sanity(game_val, output):
    """ Check if if game_val is self consistent. 

    In particular, check that the end game player decks match the result of 
    simulating deck interactions saved in game val."""

    supply = game_val.get_supply()
    if set(supply).intersection(['Masquerade', 'Black Market']):
        return True
    
    last_state = None
    game_state_iterator = game_val.game_state_iterator()
    for game_state in game_state_iterator:
        last_state = game_state
    for player_deck in game_val.get_player_decks():
        parsed_deck_comp = player_deck.Deck()
        computed_deck_comp = last_state.get_deck_composition(
            player_deck.name()) 

        delete_keys_with_empty_vals(parsed_deck_comp)
        computed_dict_comp = dict(computed_deck_comp)
        delete_keys_with_empty_vals(computed_dict_comp)
        
        if parsed_deck_comp != computed_deck_comp:
            found_something_wrong = False
            for card in set(parsed_deck_comp.keys() + 
                            computed_deck_comp.keys()):
                if parsed_deck_comp.get(card, 0) != computed_deck_comp.get(
                    card, 0):
                    if not found_something_wrong:
                        output.write('card from-data from-sim\n')
                    output.write('%s %d %d\n' % (
                            card, parsed_deck_comp.get(card, 0), 
                                computed_deck_comp.get(card, 0)))
                    found_something_wrong = True
            if found_something_wrong:
                output.write('%s %s\n' % (player_deck.name(), game_val.get_id()))
                output.write(' '.join(game_val.get_supply()))
                output.write('\n')
                return False
    return True

def main():
    #print AnnotateGame(codecs.open(fn, 'r', encoding='utf-8').read()).encode(
    #    'utf-8')
    #return
    args = utils.incremental_date_range_cmd_line_parser().parse_args()
    print args
    days = os.listdir('static/scrape_data')
    days.sort()
    for year_month_day in days:
        if not utils.includes_day(args, year_month_day):
            continue
            
        if args.incremental and os.path.exists(
            'parsed_out/%s-0.json' % year_month_day):
            print 'skipping', year_month_day, 'because already done'
            continue        

        try:
            print 'trying', year_month_day
            convert_to_json(year_month_day)
        except ParseTurnHeaderError, e:
            print e
            return

def _pretty_format_html(v):
    return '<br>' + pprint.pformat(v).replace(
        '\n', '<br>').replace(' ', '&nbsp')

def annotate_game(contents, game_id, debug=False):
    """ Decorate game contents with some JS that makes a score keeper 
    and provides anchors per turn."""
    contents = contents.replace('&mdash;', '---')
    parsed_game = parse_game(contents, dubious_check = False)
    states = []
    
    game_val = game.Game(parsed_game)
    for game_state in game_val.game_state_iterator():
        states.append(game_state.encode_game_state())

    parsed_game['game_states'] = states

    ret = u''

    start_body = contents.find('<body>') + len('<body>')
    ret += contents[:start_body]
    ret += """
<div id="game-display"></div>
<script src="static/flot/jquery.js"></script>
<script src="static/game_viewer.js"></script>
<script type="text/javascript">
        var game = %s;
        var card_list = %s;
        $(document).ready(DecorateGame);
</script>
""" % (json.dumps(parsed_game, indent=2), 
       open('static/card_list.js', 'r').read())
    contents = contents[start_body:]
    if debug > 2:
        ret += _pretty_format_html(parsed_game)
    if debug > 1:
        for turn in game_val.get_turns():
            ret += '%d %d %d %s %s<br>' % (
                turn.get_turn_no(),
                turn.get_player().TurnOrder(), turn.get_poss_no(),
                turn.turn_dict.get('poss', False),
                turn.get_player().name())

    import cStringIO as StringIO
    output_buf = StringIO.StringIO()
    if not check_game_sanity(game_val, output_buf):
        ret += 'Parsing error, data mismatch, '
        ret += '''<a href="game?game_id=%s&debug=1">be a hero, find the 
bug</a> and tell rrenaud@gmail.com<br>''' % game_id
        ret += output_buf.getvalue().replace('\n', '<br>\n')

    cur_turn_ind = 0
    
    split_turn_chunks = split_turns(contents)
    poss_num = 0
    ret += split_turn_chunks[0]
    split_turn_chunks.pop(0)

    for idx, turn_chunk in enumerate(split_turn_chunks):
        split_chunk = turn_chunk.split('\n')
        parsed_header = parse_turn_header(split_chunk[0])

        player = parsed_header['name']
        if 'turn_no' in parsed_header:
            turn_no = parsed_header['turn_no'] - 1
            # these turn id's are 0 indexed
            turn_id = '%s-turn-%d' % (player, turn_no)
            # and since these are shown, they are 1 indexed
            show_turn_id = '%s-show-turn-%d' % (player, turn_no + 1)
            poss_num = 0
        elif 'pname' in parsed_header:
            # port the turn labeller back to game.py?
            turn_id = '%s-poss-turn-%d-%d' % (player, turn_no,
                                              poss_num)
            show_turn_id = '%s-show-poss-turn-%d-%d' % (
                player, turn_no + 1, poss_num + 1)
            poss_num += 1
        else:
            assert 'outpost' in parsed_header, str(parsed_header)
            turn_id = '%s-outpost-turn-%d' % (player, turn_no)
            show_turn_id = '%s-show-outpost-turn-%d' % (
                player, turn_no + 1)
            poss_num = 0

        ret += '<div id="%s"></div>' % turn_id
        ret += '<a name="%s"></a><a href="#%s">%s</a>' % (
            show_turn_id, show_turn_id, split_chunk[0])

        if debug:
            ret += '<br>' + repr(game_val.get_turns()[cur_turn_ind]).replace(
                '\n', '<br>')
        cur_turn_ind += 1

        if idx != len(split_turn_chunks) - 1:
            ret += turn_chunk[turn_chunk.find('\n'):]
        else:            
            before_end = turn_chunk.find('</html')
            ret += turn_chunk[turn_chunk.find('\n'): before_end]
            ret += '<div id="end-game">\n'
            ret += '</div>&nbsp<br>\n' * 10  
            ret += '</html>'
    return ret
    
# def profilemain():
#     import hotshot, hotshot.stats
#     prof = hotshot.Profile("parse_game.prof")
#     prof.runcall(t)
#     prof.close()
#     stats = hotshot.stats.load("parse_game.prof")
#     stats.strip_dirs()
#     stats.sort_stats('time', 'calls')
#     stats.print_stats(20)

if __name__ == '__main__':
    utils.ensure_exists('parsed_out')
    main()
    
