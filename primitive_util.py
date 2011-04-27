#!/usr/bin/python

import collections

PRIMITIVES = [dict, str, int, list, float, unicode]

def to_primitive(val):
    if hasattr(val, 'to_primitive_object'):
        return val.to_primitive_object()
    assert type(val) in PRIMITIVES, val
    return val

#TODO: this is depending on implicit old-style class behavior
class PrimitiveConversion(object):
    def to_primitive_object(self):
        ret = {}
        for k, v in self.__dict__.iteritems():
            ret[k] = to_primitive(v)
        return ret

    def from_primitive_object(self, obj):
        # Get rid of _id because it's something that mongo injects into our
        # objects, and it's not really natural to the objects themselves.
        obj_keys_except_id = set(obj.keys()) - set(['_id'])
        unicoded_keys = set(map(unicode, self.__dict__.keys()))
        assert unicoded_keys == obj_keys_except_id, (
            '%s != %s' % (str(unicoded_keys),  str(obj_keys_except_id)))
        for k in obj_keys_except_id:
            if hasattr(self.__dict__[k], 'from_primitive_object'):
                self.__dict__[k].from_primitive_object(obj[k])
            else:
                assert type(obj[k]) in PRIMITIVES, obj[k]
                self.__dict__[k] = obj[k]


class ConvertibleDefaultDict(collections.defaultdict, PrimitiveConversion):
    def __init__(self, value_type, key_type = str):
        collections.defaultdict.__init__(self, value_type)
        self.value_type = value_type
        self.key_type = key_type

    def to_primitive_object(self):
        ret = {}
        for key, val in self.iteritems():
            if type(key) == unicode:
                key = key.encode('utf-8')
            else:
                key = str(key)
            ret[key] = to_primitive(val)
        return ret

    def from_primitive_object(self, obj):
        for k, v in obj.iteritems():
            if k == '_id': continue
            val = self.value_type()
            if hasattr(val, 'from_primitive_object'):
                val.from_primitive_object(v)
            else: 
                val = v
            self[self.key_type(k)] = val

if __name__ == '__main__':
    import pymongo
    c = pymongo.Connection()
    db = c.test
    coll = db.prim
    prim_a['_id'] = ''
    coll.save(prim_a, safe='true')

    a_from_db = list(coll.find())[0]
    new_a = A()
    new_a.from_primitive_object(a_from_db)
    assert new_a.foo == a.foo
    assert new_a.bar == a.bar

