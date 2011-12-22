""" Update trueskill ratings for openings."""

from utils import get_mongo_connection, progress_meter

import trueskill.trueskill as ts
import incremental_scanner
import primitive_util
import utils

def results_to_ranks(results):
    sorted_results = sorted(results)
    return [sorted_results.index(r) for r in results]

class PrimitiveSkillInfo(primitive_util.PrimitiveConversion):
    def to_primitive_object(self):
        return {'mu': float(self.mu),
                'sigma': float(self.sigma),
                'gamma': float(self.gamma),
                'floor': float(self.floor),
                'ceil': float(self.ceil)}

class DbBackedSkillTable(ts.SkillTable):
    def __init__(self, coll):
        ts.SkillTable.__init__(self, self._db_backed_missing_func)
        self.coll = coll
        self.skill_infos = {}

    def _db_backed_missing_func(self, name):
        if name in self.skill_infos:
            return self.skill_infos[name]
        db_data = self.coll.find_one({'_id': name})
        skill_info = PrimitiveSkillInfo()
        if db_data:
            skill_info.mu = db_data['mu']
            skill_info.sigma = db_data['sigma']
            skill_info.gamma = db_data['gamma']
        else:
            skill_info.sigma = 25.0/3
            if name.startswith('open:'):
                skill_info.gamma = 0.0001
                skill_info.mu = 0.
            else:
                skill_info.gamma = 0.
                skill_info.mu = 25.

        self.skill_infos[name] = skill_info
        return self.skill_infos[name]
    
    def add_uncertainty(self, strength, skip_openings=False):
        for key, value in self.skill_infos.iteritems():
            if not (skip_openings and key.startswith('open:')):
                value.sigma = (value.sigma*(1-strength)) + (25./3*strength)
                value.floor = value.mu - 3*value.sigma
                value.ceil = value.mu + 3*value.sigma

    def save(self):
        for key, val in self.skill_infos.iteritems():
            utils.write_object_to_db(val, self.coll, key)

def setup_openings_collection(coll):
    coll.ensure_index('_id')
    coll.ensure_index('mu')
    coll.ensure_index('floor')
    coll.ensure_index('ceil')

def update_skills_for_game(game, opening_skill_table, 
                           player_skill_table
                           ):
    teams = []
    results = []
    openings = []
    dups = False
    for deck in game['decks']:
        if len(deck['turns']) >= 2:
            opening = deck['turns'][0].get('buys', []) + \
                deck['turns'][1].get('buys', [])
        else:
            opening = ['resign']
            dups = True
            
        opening.sort()
        open_name = 'open:' + '+'.join(opening)
        if open_name in openings:
            dups = True
        openings.append(open_name)
        nturns = len(deck['turns'])
        if deck['resigned']:
            vp = -1000
        else:
            vp = deck['points']
        results.append((-vp, nturns))
        player_name = deck['name'][:80]

        teams.append([open_name, player_name])
        ranks = results_to_ranks(results)

    if not dups:
        team_results = [
            (team, [0.5, 0.5], rank)
            for team, rank in zip(teams, ranks)
            ]
        ts.update_trueskill_team(team_results, opening_skill_table)
    
    player_results = [
         ([team[1]], [1.0], rank)
         for team, rank in zip(teams, ranks)
         ]
    ts.update_trueskill_team(player_results, player_skill_table)
    
def run_trueskill_openings():
    con = get_mongo_connection()
    db = con.test
    games = db.games

    collection = db.trueskill_openings_dev
    player_collection = db.trueskill_players_dev
    
    ## if we want to start over:
    #db.scanner.remove({'_id': 'trueskill'})
    #player_collection.remove()
    #collection.remove()

    setup_openings_collection(collection)
    setup_openings_collection(player_collection)

    opening_skill_table = DbBackedSkillTable(collection)
    player_skill_table = DbBackedSkillTable(player_collection)

    args = utils.incremental_max_parser().parse_args()
    scanner = incremental_scanner.IncrementalScanner('trueskill_dev', db)
    if not args.incremental:
        scanner.reset()
        collection.drop()

    for ind, game in enumerate(
        progress_meter(scanner.scan(db.games, {}), 100)):
        if len(game['decks']) >= 2 and len(game['decks'][1]['turns']) >= 2:
            update_skills_for_game(game, opening_skill_table, player_skill_table)
                                   
        if ind == args.max_games:
            break

        if ind % 15000 == 0:
            player_skill_table.save()
            player_skill_table.add_uncertainty(0.01)
            opening_skill_table.save()
            opening_skill_table.add_uncertainty(0.01, skip_openings=True)
    
    scanner.save()
    print scanner.status_msg()

def main():
    run_trueskill_openings()

if __name__ == '__main__':
    main()
