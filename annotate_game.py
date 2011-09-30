""" Nicely render a game with deck composition viewer and some graphs of
the game as it progresses."""

import itertools
import simplejson as json

import game
import goals
import parse_game
import sofia_predict

def _pretty_format_html(v):
    return '<br>' + pprint.pformat(v).replace(
        '\n', '<br>').replace(' ', '&nbsp')

win_predictor = sofia_predict.SofiaWinPredictor('data/logreg-peg.model')

def make_graph(label, div_name):
    return """
  <tr>
    <td width=50px>%s</td>
    <td><div id="%s" style="width:1000px;height:250px;"></div></td>
  </tr>
""" % (label, div_name)

def get_goals(game):
    glist = goals.all_goals(game)
    if len(glist)==0:
        goal_contents = None
    else:
        goal_contents = '<table cellpadding="7">'
        for goal_name, output in glist.items():
            for attainer in output:
                reason = attainer['reason']
                reason = str.lower(reason[0:1]) + reason[1:]
                goal_contents += '<tr><td><img src="%s" alt="%s"><td><strong>%s</strong><br>%s %s</tr>' % (goals.GetGoalImageFilename(goal_name), goal_name, goal_name, attainer['player'], reason)
        goal_contents += '</table>'
    return "<tr><td>goals</td><td>%s</td></tr>"%goal_contents

def annotate_game(contents, game_id, debug=False):
    """ Decorate game contents with some JS that makes a score keeper 
    and provides anchors per turn."""
    contents = contents.replace('&mdash;', '---')
    parsed_game = parse_game.parse_game(contents, dubious_check = False)
    states = []
    
    game_val = game.Game(parsed_game)
    win_prob_enabled = len(game_val.get_player_decks()) == 2
    if win_prob_enabled:
        predictions = win_predictor.predict_all_turns(game_val)

    for idx, game_state in enumerate(game_val.game_state_iterator()):
        encoded = game_state.encode_game_state()
        encoded['win_prob'] = predictions[idx] if win_prob_enabled else 0
        states.append(encoded)

    parsed_game['game_states'] = states

    ret = u''

    start_body = contents.find('<body>') + len('<body>')
    ret += contents[:start_body]
    ret += """
<div id="game-display"></div>
<script src="static/flot/jquery.js"></script>
<script src="static/game_viewer.js"></script>
<script src="static/flot/jquery.js"></script>
<script src="static/flot/jquery.flot.js"></script>
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
    if not parse_game.check_game_sanity(game_val, output_buf):
        ret += 'Parsing error, data mismatch, '
        ret += '''<a href="game?game_id=%s&debug=1">be a hero, find the 
bug</a> and tell rrenaud@gmail.com<br>''' % game_id
        ret += output_buf.getvalue().replace('\n', '<br>\n')

    cur_turn_ind = 0
    
    split_turn_chunks = parse_game.split_turns(contents)
    ret += split_turn_chunks[0]
    split_turn_chunks.pop(0)

    for idx, (turn_chunk, game_state) in enumerate(
        itertools.izip(split_turn_chunks, game_val.game_state_iterator())):
        split_chunk = turn_chunk.split('\n')

        turn_id = game_state.turn_label()
        show_turn_id = game_state.turn_label(for_anchor=True)
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
            win_prob_graph = ''

            if win_prob_enabled:
                win_prob_graph = make_graph('win prob', 'win-prob-graph')
            ret += """
<div id="end-game"></div>
<table>
  %s
  %s
  %s
  %s
</table>
""" % (make_graph('score', 'score-graph'), make_graph('money', 'money-graph'),
       win_prob_graph, get_goals(game_val))
            ret += '</div>&nbsp<br>\n' * 10 
            ret += '</html>'
    return ret
