class IncrementalScanner(object):
    def __init__(self, scan_name, db):
        self.num_games = 0
        self.max_game_id = ''
        self.scan_name = scan_name
        self.db = db
        stored_info = db.scanner.find_one({'_id': scan_name})
        if stored_info:
            self.num_games = stored_info['num_games']
            self.max_game_id = stored_info['max_game_id']

    def get_max_game_id(self):
        return self.max_game_id

    def get_num_games(self):
        return self.num_games

    def status_msg(self):
        return 'Max game id %s, num games %s' % (self.max_game_id,
                                                 self.num_games)

    def reset(self):
        self.num_games = 0
        self.max_game_id = ''
        self.save()

    def scan(self, collection, query):
        assert not '_id' in query
        query['_id'] = {'$gt': self.max_game_id}
        for item in collection.find(query):
            self.max_game_id = max(item['_id'], self.max_game_id)
            self.num_games += 1
            yield item

    def save(self):
        self.db.scanner.save({'_id': self.scan_name,
                              'num_games': self.num_games,
                              'max_game_id': self.max_game_id})
