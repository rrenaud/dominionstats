#!/usr/bin/python

import csv
import simplejson as json
import sys

if __name__ == '__main__':
    out = list(csv.DictReader(open(sys.argv[1], 'r')))
    for row in out:
        for k, v in row.iteritems():
            if v == 'false':
                row[k] = False
            elif v == 'true':
                row[k] = True
    json.dump(out, open(sys.argv[2], 'w'))
