class RecordSummary(object):
    def __init__(self):
        self.record = [0, 0, 0]
        self.win_points = 0
        self.num_games = 0

    def RecordResult(self, res, win_points):
        self.record[res] += 1
        self.win_points += win_points
        self.num_games += 1

    def AvgWinPoints(self):
        if self.num_games:
            return float(self.win_points) / self.num_games
        else:
            return 0

    def DisplayWinLossTie(self):
        return '%d-%d-%d' % tuple(self.record)
