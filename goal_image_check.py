#!/usr/bin/python

import os.path
from goals import *

def main():
    for goal_name in sorted(goal_check_funcs):
        if os.path.exists('static/images/%s.png'%goal_name):
            found = 'x'
        else:
            found = ' '
        print "%-20s[%s]"%(goal_name, found)

if __name__ == '__main__':
    main()
