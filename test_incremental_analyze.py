#!/usr/bin/python

import os
import pymongo
import pprint

range_test_datas = [dict(name='r1', ranges=[('20101020', '20101021'),
                                            ('20101021', '20101022')]),
                    dict(name='r2', ranges=[('20101020', '20101022')])]

c = pymongo.Connection()

def test_incremental_build(range_test_data):
    ranges = range_test_data['ranges']
    col_name = range_test_data['name']
    print 'testing', ranges, col_name
    c.test.drop_collection(col_name)
    for mn, mx in ranges:
        cmd = ('python analyze.py --min_date=%s --max_date=%s '
               '--output_collection_name=%s' % (mn, mx, col_name))
        print cmd
        os.system(cmd)

for range_test_data in range_test_datas:
    test_incremental_build(range_test_data)

query = {'_id':''}
first_out = c.test[range_test_datas[0]['name']].find_one(query)
assert first_out
for additional_data in range_test_datas[1:]:
    name = additional_data['name']
    this_out = c.test[name].find_one(query)
    assert this_out
    assert first_out == this_out


