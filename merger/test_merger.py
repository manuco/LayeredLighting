#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest

from merger import Layer, Merger, Channel

class LayerTests(unittest.TestCase):

    def test_layer_level(self):
        l = Layer("1")
        l = Layer("1.2")
        l = Layer("1.2.3.5.5.1.3")
        l = Layer("-1")
        l = Layer("-1.6")
        l = Layer("-1.6.-3")

        try:
            l = Layer("a")
        except ValueError:
            pass
        else:
            self.fail()

        try:
            l = Layer("a.a")
        except ValueError:
            pass
        else:
            self.fail()

        try:
            l = Layer("1.a")
        except ValueError:
            pass
        else:
            self.fail()

        try:
            l = Layer("1.")
        except ValueError:
            pass
        else:
            self.fail()

        try:
            l = Layer(".1")
        except ValueError:
            pass
        else:
            self.fail()

        try:
            l = Layer("1..1")
        except ValueError:
            pass
        else:
            self.fail()

        try:
            l = Layer("")
        except ValueError:
            pass
        else:
            self.fail()


    def test_ordering_simple(self):
        l2 = Layer("2")
        l1 = Layer("1")
        self.assertTrue(l1 < l2)
        self.assertFalse(l1 > l2)
        self.assertTrue(l2 > l1)
        self.assertFalse(l2 < l1)

        l1 = Layer("1")
        l2 = Layer("2")

        self.assertTrue(l1 < l2)
        self.assertFalse(l1 > l2)
        self.assertTrue(l2 > l1)
        self.assertFalse(l2 < l1)


    def test_ordering(self):
        self.assertTrue(Layer("2") > Layer("1"))
        self.assertTrue(Layer("2") > Layer("1.9"))
        self.assertTrue(Layer("2.1") > Layer("2"))
        self.assertTrue(Layer("2.1.1.2") > Layer("2.1.1.1"))
        self.assertTrue(Layer("2.2") > Layer("2.1.1.1"))
        self.assertTrue(Layer("-1") > Layer("2.1.1.1"))
        self.assertTrue(Layer("-2") > Layer("-1"))
        self.assertTrue(Layer("-2.-1") > Layer("-2.99"))

    def test_ordering_list(self):
        l2 = Layer("2")
        l11 = Layer("1.1")
        l = [
            l2,
            l11,
        ]
        l.sort()
        self.assertEqual(l, [l11, l2])

        l11 = Layer("1.1")
        l2 = Layer("2")
        l = [
            l2,
            l11,
        ]
        l.sort()
        self.assertEqual(l, [l11, l2])


        lm1 = Layer("-1")
        l11 = Layer("1.1")
        l2 = Layer("2")
        l = [
            l2,
            lm1,
            l11,
        ]
        l.sort()
        self.assertEqual(l, [l11, l2, lm1])



class MergerTests(unittest.TestCase):

    def test_adding_layers(self):

        m = Merger()
        l = Layer("1")
        m.addLayer(l)
        self.assertEqual(m.layers, [l])


        m = Merger()
        l = Layer("1")
        l2 = Layer("1")
        m.addLayer(l)
        m.addLayer(l2)

        self.assertEqual(m.layers, [l2])

        m.delLayer(l2)
        m.delLayer(l)

    def test_merge_simple(self):
        m = Merger()
        l = Layer("1")

        l.addChannel(1, 255)
        l.addChannel(2, 127)

        m.addLayer(l)
        m.merge()
        self.assertEqual(m.galaxy[1], 255)
        self.assertEqual(m.galaxy[2], 127)


    def test_merge_complete(self):
        m = Merger()
        l1 = Layer("1")
        l1.addChannel(2, 1)
        l1.addChannel(3, 255)
        l1.addChannel(4, 127)
        
        l2 = Layer("2")
        l2.addChannel(3, 0, 0.5)
        l2.addChannel(4, 255, "max")
        l2.addChannel(5, 255, "min")
        
        l3 = Layer("3")
        l3.addChannel(2, 255, 0.3)
        
        l4 = Layer("4")
        l4.addChannel(2, 127, 0.6)

        m.addLayer(l1)
        m.addLayer(l2)
        m.addLayer(l3)
        m.addLayer(l4)
        m.merge()

        self.assertEqual(m.galaxy[1], 0)
        self.assertEqual(m.galaxy[2], 107)
        self.assertEqual(m.galaxy[3], 128)
        self.assertEqual(m.galaxy[4], 255)
        self.assertEqual(m.galaxy[5], 0)



if __name__ == "__main__":
    unittest.main()

    