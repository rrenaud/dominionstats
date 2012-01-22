import os
import time
from datetime import date
import utils 

import sys

utils.ensure_exists('static/status')

cmds = [
    'python scrape.py',            # downloads gamelogs from isotropic
    'python parse_game.py',        # parses data into useable format
    'python load_parsed_data.py',  # loads data into database
    'python analyze.py',           # produces data for graphs
    'python goals.py',
    'python count_buys.py',
    'python run_trueskill.py',
    'python optimal_card_ratios.py',
]

extra_args = sys.argv[1:]

# should think about how to parrallelize this for multiprocessor machines.
while True:
    for cmd in cmds:
        status_fn = (cmd.replace(' ', '_') + '-' + 
                     date.today().isoformat() + '-' +
                     time.strftime('%H:%M:%S') + '.txt')
        cmd = cmd + ' ' + ' '.join(extra_args) + ' 2>&1 | tee -a ' + status_fn
        print cmd
        os.system(cmd)
        os.system('mv %s static/status' % status_fn)
    print 'sleeping'
    time.sleep(60*15)  # try to update every 15 mins

