# -*- coding: utf-8 -*-

import sys, os
sys.path.append(os.path.join(".."))

import unittest

from model import JSonSerialisableObject, parse, buildObject, register


class A(JSonSerialisableObject):
    def __init__(self):
        self.register_attrs("b", "c")
register("A", A)

class D(JSonSerialisableObject):
    def __init__(self):
        self.register_attrs("e", "f")
register("D", D)



class BuilderTests(unittest.TestCase):
    def test_1(self):
        a = A()
        a.b = 1

        d = D()
        d.e = 2
        d.f = 3

        a.c = d

        self.assertEquals(a.attrs, ("b", "c"))
        self.assertEquals(d.attrs, ("e", "f"))

    def test_2(self):
        stream1 = {
            "kind": "A",
            "attrs": {"b": 1},
            "refs": {"refToD": "c"}
        }
        a = parse(stream1)
        self.assertEquals(a.b, 1)
        self.assertEquals(a.pendingRefs, {"refToD": "c"})


if __name__ == "__main__":
    unittest.main()

    