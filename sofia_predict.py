import subprocess

import pymongo

import game
import game_state_features
import math

def log_odds_to_prob(logodds):
    odds = math.exp(logodds)
    return odds / (1 + odds)

def encode_features_for_all_turns(game_val):
    return [game_state_features.state_to_features(game_val, game_state)
            for game_state in game_val.game_state_iterator()]

class SofiaWinPredictor:
    def __init__(self, model_name, prediction_type='logistic', 
                 hash_mask_bits=None):
        self.use_sofia = not subprocess.call(['which', 'sofia-ml'], stdout=subprocess.PIPE)
        if not self.use_sofia:
            return

        args = ['sofia-ml', 
                '--model_in', model_name, 
                '--test_stream',
                '--prediction_type', prediction_type]
        if hash_mask_bits is not None:
            args.extend(['--hash_mask_bits', str(hash_mask_bits)])
        p = subprocess.PIPE
        self.sofia_proc = subprocess.Popen(args, stdin=p, stdout=p)

    def predict_all_turns(self, game_val):
        ret = []
        all_turns_features = encode_features_for_all_turns(game_val)

        if self.use_sofia:
            for features in all_turns_features:
                game_state_features.output_libsvm_state(features, 
                                                        self.sofia_proc.stdin)

            for _ in all_turns_features:
                line = self.sofia_proc.stdout.readline()
                # print line,
                ret.append(log_odds_to_prob(float(line)))
        else:
            for _ in all_turns_features:
                ret.append(0.5)
        return ret

def main():
    c = pymongo.Connection()
    g = game.Game(c.test.games.find_one())
    predictor = SofiaWinPredictor('data/logreg-peg.model')
    print predictor.predict_all_turns(g)

if __name__ == '__main__':
    main()
