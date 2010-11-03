# -*- coding: utf-8 -*-

import sys, os
sys.path.append(os.path.join(".."))

import unittest

from model import JSonSerialisableObject, parse, buildObject, register, serialize


class A(JSonSerialisableObject):
    def __init__(self):
        self.register_attrs("b", "c")
register("A", A)

class D(JSonSerialisableObject):
    def __init__(self):
        self.register_attrs("e", "f")
register("D", D)

class G(JSonSerialisableObject): pass
register("G", G)

class L(JSonSerialisableObject):
    def __init__(self):
        self.register_attrs("l")


class BuilderTests(unittest.TestCase):
    def test_1(self):
        a = A()
        a.b = 1

        d = D()
        d.e = 2
        d.f = 3

        a.c = d

        self.assertEquals(a.attrs, set(("b", "c")))
        self.assertEquals(d.attrs, set(("e", "f")))

    def test_2(self):
        stream1 = {
            "kind": "A",
            "attrs": {"b": 1},
            "refs": {"refToD": "c"},
            "uid": "a",
        }

        a, missing = buildObject(None, stream1)
        self.assertEquals(a.b, 1)
        self.assertEquals(a.pendingRefs, {"refToD": "c"})
        self.assertEquals(missing, ["refToD"])

        stream2 = {
            "kind": "D",
            "attrs": {"e": 2, "f": 3},
            "uid": "refToD",
        }

        b, missing = buildObject(a, stream2)
        self.assertTrue(a is b)
        self.assertEquals(a.b, 1)
        self.assertEquals(missing, [])
        self.assertTrue(hasattr(a, "c"))
        self.assertEquals(a.c.e, 2)
        self.assertEquals(a.c.f, 3)


    def test_3(self):
        stream1 = {
            "kind": "G",
            "uid": "g",
        }

        obj, missing = buildObject(None, stream1)

    def test_4(self):
        stream1 = {
            "kind": "A",
            "refs": {"refTob": "b", "reftoc": "c"},
            "uid": "a",
        }

        obj, missing = buildObject(None, stream1)
        self.assertEquals(set(missing), set(["refTob", "reftoc"]))

        stream2 = {
            "kind": "A",
            "attrs": {"c": 3},
            "refs": {"refTob2": "b"},
            "uid": "reftoc",
        }

        obj, missing = buildObject(obj, stream2)
        self.assertEquals(set(missing), set(["refTob2", "refTob"]))
        self.assertTrue(hasattr(obj, "c"))
        self.assertEquals(obj.c.c, 3)

        stream3 = {
            "kind": "A",
            "attrs": {"b": 2, "c": 1},
            "uid": "refTob2",
        }

        obj, missing = buildObject(obj, stream3)
        self.assertEquals(set(missing), set(["refTob"]))
        
        stream4 = {
            "kind": "A",
            "attrs": {"b": 4, "c": 5},
            "uid": "refTob",
        }

        obj, missing = buildObject(obj, stream4)
        self.assertEquals(missing, [])

        self.assertEquals(obj.b.b, 4)
        self.assertEquals(obj.b.c, 5)
        self.assertEquals(obj.c.b.b, 2)
        self.assertEquals(obj.c.b.c, 1)
        self.assertEquals(obj.c.c, 3)


    def test_serialization(self):
        a = A()
        a.b = 1

        d = D()
        d.e = 2
        d.f = 3

        a.c = d

        streams = serialize(a, "a")
        self.assertEquals(streams,
            [
                {"kind": "D", "attrs": {"e": 2, "f": 3}, "uid": "a.c"},
                {"kind": "A", "attrs": {"b": 1}, "uid": "a", "refs": {"a.c": "c"}},
            ]
        )

    def test_lists(self):
        ## XXX stand by
        return
        stream1 = {"kind": "L", "uid": "l", "lists": {"l": 2}}
        obj, missing = buildObject(None, stream1)
        self.assertEquals(set(missing), set(["l.l.0", "l.l.1"]))
        

    def test_serialization_lists(self):
        ## XXX stand by
        return
        a1 = A()
        a1.b = 1
        a1.c = 2

        a2 = A()
        a2.b = 3
        a2.c = 4

        l = L()
        l.l = [a1, a2]
        streams = serialize(l, "l")
        self.assertEquals(streams,
            [
                {"kind": "A", "attrs": {"b": 1, "c": 2}, "uid": "l.l.0"},
                {"kind": "A", "attrs": {"b": 3, "c": 4}, "uid": "l.l.1"},
                {"kind": "L", "uid": "l", "lists": {"l": 2}},
            ]
        )


if __name__ == "__main__":
    unittest.main()

    