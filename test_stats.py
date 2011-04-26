#!/usr/bin/python

import unittest
import stats

class RandomVariableStat(unittest.TestCase):
    def testSimple(self):
        d = stats.MeanVarStat()
        d.AddOutcome(4)  # 10 - 4 = 6, 6^2 = 36
        d.AddOutcome(16) # 16 - 10 = 6, 6^2 = 36
        d.AddOutcome(13) # 13 - 10 = 3, 3^2 = 9
        d.AddOutcome(7)  # 10 - 7 = 3, 3^2 = 9
        #  36 + 36 + 9 + 9 = 90, 90 / 3 = 30
        self.assertEquals(d.Frequency(), 4)
        self.assertEquals(d.Mean(), 10)
        self.assertEquals(d.Variance(), 30.0)

if __name__ == '__main__':
    unittest.main()
