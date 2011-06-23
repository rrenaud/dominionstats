#!/usr/bin/python

import unittest
import game

class ScoreDeckTest(unittest.TestCase):
    def test_gardens(self):
        self.assertEquals(game.score_deck({'Gardens': 1, 'Copper': 9}), 1)
        self.assertEquals(game.score_deck({'Gardens': 2, 'Copper': 8}), 2)
        self.assertEquals(game.score_deck({'Gardens': 2, 'Copper': 7}), 0)

    def test_fairgrounds(self):
        self.assertEquals(game.score_deck({'Fairgrounds': 1,
                                           'Copper': 1,
                                           'Silver': 1,
                                           'Gold': 1,
                                           'Bank': 1}), 2)

    def test_duke(self):
        self.assertEquals(game.score_deck({'Duke': 2, 'Duchy': 2}), 10)

    def test_simple(self):
        return self.assertEquals(game.score_deck({
                    'Curse': 1, 'Estate': 1, 'Duchy': 1, 
                    'Province': 1, 'Colony': 1}), 19)
                    

if __name__ == '__main__':
    unittest.main()
