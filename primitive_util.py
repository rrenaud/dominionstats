#!/usr/bin/python

import collections

PRIMITIVES = [dict, str, int, list, float, unicode]

def ToPrimitive(val):
    if hasattr(val, 'ToPrimitiveObject'):
        return val.ToPrimitiveObject()
    assert type(val) in PRIMITIVES, val
    return val

class PrimitiveConversion(object):
    def ToPrimitiveObject(self):
        ret = {}
        for k, v in self.__dict__.iteritems():
            ret[k] = ToPrimitive(v)
        return ret

    def FromPrimitiveObject(self, obj):
        # Get rid of _id because it's something that mongo injects into our
        # objects, and it's not really natural to the objects themselves.
        obj_keys_except_id = set(obj.keys()) - set(['_id'])
        unicoded_keys = set(map(unicode, self.__dict__.keys()))
        assert unicoded_keys == obj_keys_except_id, (
            '%s != %s' % (str(unicoded_keys),  str(obj_keys_except_id)))
        for k in obj_keys_except_id:
            if hasattr(self.__dict__[k], 'FromPrimitiveObject'):
                self.__dict__[k].FromPrimitiveObject(obj[k])
            else:
                assert type(obj[k]) in PRIMITIVES, obj[k]
                self.__dict__[k] = obj[k]

class ConvertibleDefaultDict(PrimitiveConversion):
    def __init__(self, value_type, key_type = str):
        self.value_type = value_type
        self.key_type = key_type
        self.backing_dict = collections.defaultdict(value_type)

    def __getattr__(self, key):
        return getattr(self.backing_dict, key)

    def ToPrimitiveObject(self):
        ret = {}
        for key, val in self.backing_dict.iteritems():
            if type(key) == unicode:
                key = key.encode('utf-8')
            else:
                key = str(key)
            ret[key] = ToPrimitive(val)
        return ret

    def FromPrimitiveObject(self, obj):
        for k, v in obj.iteritems():
            if k == '_id': continue
            val = self.value_type()
            if hasattr(val, 'FromPrimitiveObject'):
                val.FromPrimitiveObject(v)
            else: 
                val = v
            self.backing_dict[self.key_type(k)] = val

    def __eq__(self, obj):
        return self.backing_dict == obj.backing_dict

if __name__ == '__main__':
    import pymongo
    c = pymongo.Connection()
    db = c.test
    coll = db.prim
    prim_a['_id'] = ''
    coll.save(prim_a, safe='true')

    a_from_db = list(coll.find())[0]
    new_a = A()
    new_a.FromPrimitiveObject(a_from_db)
    assert new_a.foo == a.foo
    assert new_a.bar == a.bar

