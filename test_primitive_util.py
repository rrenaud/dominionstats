#!/usr/bin/python

import unittest
import primitive_util

class SimpleConversion(unittest.TestCase):
    def test(self):
        class A(primitive_util.PrimitiveConversion):
            def __init__(self):
                self.foo = int()
                self.bar = str()

        a = A()
        a.foo = 3
        a.bar = 'baz'

        prim_a = a.to_primitive_object()
        returned_a = A()
        returned_a.from_primitive_object(prim_a)

        self.assertEquals(returned_a.foo, a.foo)
        self.assertEquals(returned_a.bar, a.bar)

class ConvertibleDefaultDictTest(unittest.TestCase):
    def test(self):
        a = primitive_util.ConvertibleDefaultDict(str)
        a['foo'] = 3
        
        prim_a = a.to_primitive_object()
        returned_a = primitive_util.ConvertibleDefaultDict(str)
        returned_a.from_primitive_object(prim_a)
        self.assertEquals(a, returned_a)

    def testNestedCDD(self):
        CDD = primitive_util.ConvertibleDefaultDict
        x = CDD(value_type = lambda: CDD(value_type = int))
        x['foo']['bar'] = 2
        
        prim_x = x.to_primitive_object()
        self.assertEquals(prim_x, {'foo': {'bar': 2}})
        returned_x = CDD(value_type = lambda: CDD(value_type = int))
        returned_x.from_primitive_object(prim_x)
        self.assertEquals(x, returned_x)

class NestedClassPrimTest(unittest.TestCase):
    def test(self):
        class B(primitive_util.PrimitiveConversion):
            def __init__(self):
                self.foo = int()

        class A(primitive_util.PrimitiveConversion):
            def __init__(self):
                self.d = primitive_util.ConvertibleDefaultDict(B)

        a = A()
        a.d['1'].foo = 1
        a.d['2'].foo = 4

        prim_a = a.to_primitive_object()
        returned_a = A()
        returned_a.from_primitive_object(prim_a)

        self.assertEquals(a.d['1'].foo, returned_a.d['1'].foo)
        again_prim_a = returned_a.to_primitive_object()
        self.assertEquals(prim_a, again_prim_a)

if __name__ == '__main__':
    unittest.main()
