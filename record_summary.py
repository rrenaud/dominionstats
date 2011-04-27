class RecordSummary(object):
    def __init__(self):
        self.record = [0, 0, 0]
        self.win_points = 0
        self.num_games = 0

    def record_result(self, res, win_points):
        self.record[res] += 1
        self.win_points += win_points
        self.num_games += 1

    def average_win_points(self):
        if self.num_games:
            return float(self.win_points) / self.num_games
        else:
            return 0

    def display_win_loss_tie(self):
        return '%d-%d-%d' % tuple(self.record)
