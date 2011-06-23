#!/usr/bin/python

import datetime
import argparse
import os
import time
import ConfigParser
import pymongo

def get_mongo_connection():
   mongo_connection = 'localhost'

   try:
      config = ConfigParser.ConfigParser()
      config.read('conf.ini')

      mongo_connection = config.get('mongo', 'connection')
   #FIXME: this is too broad
   except:
      pass

   return pymongo.Connection(mongo_connection)

# Should I read once somewhere and cache?  I guess when
#   we have more config things.
def get_mongo_database():
   connection = get_mongo_connection()

   db = None
   try:
      config = ConfigParser.ConfigParser()
      config.read('conf.ini')

      db = connection[config.get('mongo', 'database')]
   except:
      db = connection['test']

   return db

def read_object_from_db(obj, collection, _id):
   prim = collection.find_one({'_id': _id})
   if prim:
      obj.from_primitive_object(prim)

def write_object_to_db(obj, collection, _id):
    prim = obj.to_primitive_object()
    prim['_id'] = _id
    collection.save(prim)

def ensure_exists(path):
    if not os.path.exists(path):
        os.makedirs(path)

def at_least_as_big_as(path, min_file_size):
    if not os.path.exists(path):
        return False
    return os.stat(path).st_size >= min_file_size

def daterange(start_date, end_date):
    for n in range((end_date - start_date).days):
        yield start_date + datetime.timedelta(n)

def incremental_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--noincremental', action='store_false', 
                        dest='incremental')
    return parser

def incremental_max_parser():
   parser = incremental_parser()
   parser.add_argument('--max_games', default=-1, type=int)
   return parser

def incremental_date_range_cmd_line_parser():
    parser = incremental_parser()
    # 20101015 is the first day with standard turn labels
    parser.add_argument('--startdate', default='20101015')
    parser.add_argument('--enddate', default='99999999')
    return parser

def includes_day(args, str_yyyymmdd):
    assert len(str_yyyymmdd) == 8, '%s not 8 chars' % str_yyyymmdd
    return args.startdate <= str_yyyymmdd <= args.enddate 

def progress_meter(iterable, chunksize):
    """ Prints progress through iterable at chunksize intervals."""
    scan_start = time.time()
    since_last = time.time()
    for idx, val in enumerate(iterable):
        if idx % chunksize == 0 and idx > 0: 
            print idx
            print 'avg rate', idx / (time.time() - scan_start)
            print 'inst rate', chunksize / (time.time() - since_last)
            since_last = time.time()
            print
        yield val
