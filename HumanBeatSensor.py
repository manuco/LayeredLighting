#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import division

import time, datetime
import math
import sys

from PyQt4.Qt import *


STEPS_BEFORE_COMPUTE = 3
MAX_DEVIATION = 3
MAX_STEPS = 4 * 8

class HBSUi(QWidget):
    def __init__(self, hbs, *args):
        QWidget.__init__(self, *args)
        self.prepareUi()
        self.hbs = hbs
        self.nextBeat = 0
        self.connect(self.beatButton, SIGNAL("pressed()"), self.beat)
        self.beatPerMesure = 4
        self.prepareTimers()

    def prepareUi(self):
        self.beatButton = QPushButton()
        self.beatButton.setText("Beat")
        self.beatButton.setMinimumWidth(100)
        self.beatButton.setMinimumHeight(50)
        self.layout = QVBoxLayout(self)
        self.label = QLabel()
        self.stats = QLabel()
        self.beatLabel = QLabel(" ")
        self.layout.addWidget(self.beatButton)
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.stats)
        self.layout.addWidget(self.beatLabel)

    def prepareTimers(self):
        self.lightOnTimer = QTimer()
        self.lightOffTimer = QTimer()
        self.stateTimer = QTimer()
        self.lightOnTimer.setSingleShot(True)
        self.lightOffTimer.setSingleShot(True)
        self.stateTimer.setSingleShot(True)
        self.connect(self.lightOnTimer, SIGNAL("timeout()"), self.beatOn)
        self.connect(self.lightOffTimer, SIGNAL("timeout()"), self.beatOff)
        self.connect(self.stateTimer, SIGNAL("timeout()"), self.refreshState)

    def beatOn(self):
        self.beatLabel.setText("B - %d" % ((self.beatCount % self.beatPerMesure) + 1))
        self.lightOffTimer.start()
        self.beatCount += 1
        if self.hbs.state == "adjusting":
            self.nextBeat += self.hbs.beatLength
        tmout = int((self.nextBeat - time.time()) * 1000)
        if tmout > 0:
            self.lightOnTimer.start(tmout)

    def beatOff(self):
        if self.hbs.state == "adjusting":
            self.beatLabel.setText("   - %d" % ((self.beatCount % self.beatPerMesure) + 1))
        else:
            self.beatLabel.setText("")

    def beat(self):
        self.hbs.beat()

        tc = time.time()
        if self.hbs.state == "adjusting":
            self.lightOffTimer.setInterval((self.hbs.beatLength / 6) * 1000)
            self.nextBeat = tc
            self.beatOn()

        if self.hbs.timeout > tc:
            self.stateTimer.setInterval((self.hbs.timeout - tc) * 1000)
            self.stateTimer.start()

        if len(self.hbs.timecodes) == 1:
            self.beatCount = 0

        self.label.setText(self.hbs.state)
        self.stats.setText("Bpm: %d\tDev: %0.2f" % (self.hbs.bpm, self.hbs.deviation))

    def refreshState(self):
        self.label.setText("ready")

class HumanBeatSensor(object):
    def __init__(self):
        self.state = "ready"
        self.timecodes = None
        self.deviation = 1000
        self.bpm = 0

    def getTime(self):
        return time.time()

    def beat(self):
        tc = self.getTime()
        if tc > self.timeout:
            self.state = "ready"
            self.bpm = 0
            self.deviation = 1000

        if self.state == "ready":
            self.timecodes = [tc]
            self.timeout = tc + 3
            self.state = "acquiring"
        elif self.state == "acquiring":
            self.timecodes += [tc]
            if len(self.timecodes) >= STEPS_BEFORE_COMPUTE:
                self.state = "learning"
                self.computeData(tc)
            else:
                self.timeout = tc + 3
        elif self.state == "learning":
            self.timecodes += [tc]
            if len(self.timecodes) > MAX_STEPS:
                self.timecodes = self.timecodes[-12:]
            self.computeData(tc)
            if self.deviation < MAX_DEVIATION:
                self.state = "adjusting"
        elif self.state == "adjusting":
            self.timecodes += [tc]
            if len(self.timecodes) > MAX_STEPS:
                self.timecodes = self.timecodes[-12:]
            self.computeData(tc)


    def computeIntervals(self):
        t1 = self.timecodes[:-1]
        t2 = self.timecodes[1:]
        return [b -a for a, b in zip(t1, t2)]

    def computeAverage(self, intervals):
        return math.fsum(intervals) / len(intervals)

    def computeDeviation(self, intervals, average):
        return math.sqrt(math.fsum([(v - average) ** 2 for v in intervals]) / len(intervals)) / average

    def computeData(self, tc):
        intervals = self.computeIntervals()
        average = self.computeAverage(intervals)
        deviation = self.computeDeviation(intervals, average) * 50
        self.bpm = int((1 / average) * 60)
        self.deviation = deviation
        self.beatLength = average
        self.timeout = tc + self.beatLength * 2

    def timeout(self):
        pass


def main():
    hbs = HumanBeatSensor()

    app = QApplication(sys.argv)
    pyqtRemoveInputHook()

    ui = HBSUi(hbs)
    ui.show()

    app.exec_()


if "__main__" == __name__:
    main()

    