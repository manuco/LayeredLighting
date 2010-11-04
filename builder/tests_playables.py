#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, os
sys.path.append(os.path.join(".."))

import unittest

#from builder import Builder
from model.objects import ChannelInfo, Length, Effect, Scene, Step, Sequence, MultiSequenceItem, MultiSequence, TimeCode

class LayerTests(unittest.TestCase):

    def test_timecode_1(self):
        # time in millis
        # beat length in millis
        # beat count per measure
        # time for first bar
        tc = TimeCode(0, 500, 4, 0)

        self.assertEqual(tc.time, 0)
        self.assertEqual(tc.measureTime, 0)
        self.assertEqual(tc.beatTime, 0)
        self.assertEqual(tc.beat, 0)
        self.assertEqual(tc.normBeat, 0)
        self.assertEqual(tc.measure, 0)
        self.assertEqual(tc.beatInMeasure, 0)
        self.assertEqual(tc.measureLength, 2000)
        self.assertEqual(tc.beatLength, 500)
        self.assertEqual(tc.beatPerMeasure, 4)

        self.assertEqual(tc.tc, (0, 0, 0, 0, 0, 0, 0, 2000, 500, 4))

    def test_timecode_2(self):
        tc = TimeCode(250, 500, 4, 0)

        self.assertEqual(tc.time, 250)
        self.assertEqual(tc.measureTime, 250)
        self.assertEqual(tc.beatTime, 250)
        self.assertEqual(tc.beat, 0)
        self.assertEqual(tc.normBeat, 0)
        self.assertEqual(tc.measure, 0)
        self.assertEqual(tc.beatInMeasure, 0)

        self.assertEqual(tc.tc, (250, 250, 250, 0, 0, 0, 0, 2000, 500, 4))

    def test_timecode_3(self):
        tc = TimeCode(1250, 500, 4, 0)

        self.assertEqual(tc.time, 1250)
        self.assertEqual(tc.measureTime, 1250)
        self.assertEqual(tc.beatTime, 250)
        self.assertEqual(tc.beat, 2)
        self.assertEqual(tc.normBeat, 2)
        self.assertEqual(tc.measure, 0)
        self.assertEqual(tc.beatInMeasure, 2)

        self.assertEqual(tc.tc, (1250, 1250, 250, 2, 2, 0, 2, 2000, 500, 4))

    def test_timecode_4(self):
        tc = TimeCode(2750, 500, 4, 0)

        self.assertEqual(tc.time, 2750)
        self.assertEqual(tc.measureTime, 750)
        self.assertEqual(tc.beatTime, 250)
        self.assertEqual(tc.beat, 5)
        self.assertEqual(tc.normBeat, 5)
        self.assertEqual(tc.measure, 1)
        self.assertEqual(tc.beatInMeasure, 1)

        self.assertEqual(tc.tc, (2750, 750, 250, 5, 5, 1, 1, 2000, 500, 4))

    def test_timecode_5(self):
        tc = TimeCode(4000, 500, 4, 0)

        self.assertEqual(tc.time, 4000)
        self.assertEqual(tc.measureTime, 0)
        self.assertEqual(tc.beatTime, 0)
        self.assertEqual(tc.beat, 8)
        self.assertEqual(tc.normBeat, 8)
        self.assertEqual(tc.measure, 2)
        self.assertEqual(tc.beatInMeasure, 0)

        self.assertEqual(tc.tc, (4000, 0, 0, 8, 8, 2, 0, 2000, 500, 4))

    def test_timecode_offset_1(self):
        tc = TimeCode(0, 500, 4, 250)
        self.assertEqual(tc.tc, (0, 1750, 250, 0, 3, 0, 3, 2000, 500, 4))

    def test_timecode_offset_2(self):
        tc = TimeCode(250, 500, 4, 250)
        self.assertEqual(tc.tc, (250, 0, 0, 1, 4, 1, 0, 2000, 500, 4))

    def test_timecode_offset_3(self):
        tc = TimeCode(1250, 500, 4, 250)
        self.assertEqual(tc.tc, (1250, 1000, 0, 3, 6, 1, 2, 2000, 500, 4))

    def test_timecode_offset_4(self):
        tc = TimeCode(1500, 500, 4, 250)
        self.assertEqual(tc.tc, (1500, 1250, 250, 3, 6, 1, 2, 2000, 500, 4))

    def test_timecode_offset_5(self):
        tc = TimeCode(2250, 500, 4, 250)
        self.assertEqual(tc.tc, (2250, 0, 0, 5, 8, 2, 0, 2000, 500, 4))

    def test_timecode_offset_5(self):
        tc = TimeCode(2875, 500, 4, 250)
        self.assertEqual(tc.tc, (2875, 625, 125, 6, 9, 2, 1, 2000, 500, 4))


    def test_timecode_offset_7(self):
        tc = TimeCode(2875, 500, 4, 250)

        self.assertEqual(tc.time, 2875)
        self.assertEqual(tc.measureTime, 625)
        self.assertEqual(tc.beatTime, 125)
        self.assertEqual(tc.beat, 6)
        self.assertEqual(tc.normBeat, 9)
        self.assertEqual(tc.measure, 2)
        self.assertEqual(tc.beatInMeasure, 1)

        self.assertEqual(tc.tc, (2875, 625, 125, 6, 9, 2, 1, 2000, 500, 4))


    def test_timecode_anybartime_1(self):
        tc = TimeCode(5250, 500, 4, 7250)
        self.assertEqual(tc.tc, (5250, 0, 0, 11, 12, 3, 0, 2000, 500, 4))

    def test_timecode_anybartime_2(self):
        tc = TimeCode(6750, 500, 4, 7250)
        self.assertEqual(tc.tc, (6750, 1500, 0, 14, 15, 3, 3, 2000, 500, 4))

    def test_timecode_anybartime_3(self):
        tc = TimeCode(10750, 500, 4, 7250)
        self.assertEqual(tc.tc, (10750, 1500, 0, 22, 23, 5, 3, 2000, 500, 4))


    def test_timecode_negative_1(self):
        tc = TimeCode(5250, 500, 4, 7250)
        self.assertEqual(tc.tc, (5250, 0, 0, 11, 12, 3, 0, 2000, 500, 4))



    def test_1(self):
        return
        """
            Show is :
            0 -> 1500, nothing
            1500 -> 3000, fade in scene
            3000 -> 7500, scene
                ch 1: 255
                ch 2: 127
                ch 3: 5! # ! stands for not affected by fades
            7500 -> 8000, fade out
            8000 -> 10000, nothing
        """

        sc = Scene()
        sc.add_channel_info(ChannelInfo.channel(1, 255))
        sc.add_channel_info(ChannelInfo.channel(2, 127))
        sc.add_channel_info(ChannelInfo.channel(3, 5, False))

        sc.setFadeInLength(1500)
        sc.setFadeOutLength(500)

        ms = MultiSequence()
        ms.addPlayable(MultiSequenceItem.playable(sc, 1500))

        #tc


if __name__ == "__main__":
    unittest.main()



