#!/usr/bin/python

import unittest

import mergeable

class MyMergeableObject(mergeable.MergeableObject):
    pass

class MergeableTest(unittest.TestCase):
    def testBasic(self):
        a = MyMergeableObject()
        a.foo = 3

        b = MyMergeableObject()
        b.foo = 7

        a.Merge(b)
        self.assertEquals(a.foo, 10)

    def testCopyMissingAttr(self):
        a = MyMergeableObject()
        b = MyMergeableObject()
        a.foo = 'bar'
        b.baz = 'x'

        a.Merge(b)
        self.assertEquals(a.foo, 'bar')
        self.assertEquals(a.baz, 'x')

    def testNesting(self):
        a = MyMergeableObject()
        b = MyMergeableObject()
        b.c = MyMergeableObject()
        b.c.foo = 5
        
        a.c = MyMergeableObject()
        a.c.foo = 10

        b.only_here = MyMergeableObject()
        b.only_here.bar = 20
        a.Merge(b)
        self.assertEquals(a.c.foo, 15)
        self.assertEquals(a.only_here.bar, 20)

class MyMergeableDict(dict, mergeable.MergeableDict):
    pass

class MergeDictTest(unittest.TestCase):
    def testSimple(self):
        a = MyMergeableDict()
        b = MyMergeableDict()

        a['foo'] = 3
        b['bar'] = 3

        a.Merge(b)
        self.assertEquals(a['bar'], 3)

class MixedMergeTest(unittest.TestCase):
    def testMixed(self):
        a = MyMergeableObject()
        a.b = MyMergeableDict()
        a.b['c'] = 'bar'
        a.b['d'] = MyMergeableObject()
        a.b['d'].e = 1  # yo dawg

        b = MyMergeableObject()
        b.b = MyMergeableDict()
        b.b['d'] = MyMergeableObject()
        b.b['d'].e = 3

        b.b['f'] = 'foo'

        a.Merge(b)
        self.assertEquals(a.b['d'].e, 4)
        self.assertEquals(a.b['f'], 'foo')

if __name__ == '__main__':
    unittest.main()
