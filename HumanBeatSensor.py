#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import division

import time, datetime
import math
import sys

from PyQt4.Qt import *


STEPS_BEFORE_COMPUTE = 3
MAX_DEVIATION = 3
MAX_STEPS = 4 * 4

class HBSUi(QWidget):
    def __init__(self, hbs, *args):
        QWidget.__init__(self, *args)
        self.prepareUi()
        self.hbs = hbs

        self.connect(self.beatButton, SIGNAL("pressed()"), self.beat)

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
        self.lightOffTimer.setSingleShot(True)
        self.stateTimer.setSingleShot(True)
        self.connect(self.lightOnTimer, SIGNAL("timeout()"), self.beatOn)
        self.connect(self.lightOffTimer, SIGNAL("timeout()"), self.beatOff)
        self.connect(self.stateTimer, SIGNAL("timeout()"), self.refreshState)

    def beatOn(self):
        self.beatLabel.setText("B")
        self.lightOffTimer.start()

    def beatOff(self):
        self.beatLabel.setText(" ")

    def beat(self):
        self.hbs.beat()
        if self.hbs.deviation < MAX_DEVIATION:
            self.lightOffTimer.setInterval((self.hbs.beatLength / 4) * 1000)
            self.lightOnTimer.setInterval(self.hbs.beatLength * 1000)
            self.lightOnTimer.start()
        else:
            self.lightOffTimer.setInterval(500)
            self.lightOnTimer.stop()
        self.beatOn()
        tc = time.time()
        if self.hbs.timeout > tc:
            self.label.setText(self.hbs.state)
            self.stateTimer.setInterval((self.hbs.timeout - tc) * 1000)
            self.stateTimer.start()

    def refreshState(self):
        self.label.setText("ready")

class HumanBeatSensor(object):
    def __init__(self):
        self.state = "ready"
        print "ready"
        self.timecodes = None
        self.deviation = 1000

    def getTime(self):
        return time.time()

    def beat(self):
        tc = self.getTime()
        if tc > self.timeout:
            self.state = "ready"
            print "ready"

        if self.state == "ready":
            self.timecodes = [tc]
            self.timeout = tc + 3
            self.state = "learning"
            print "learning"
        elif self.state == "learning":
            self.timecodes += [tc]
            if len(self.timecodes) >= STEPS_BEFORE_COMPUTE:
                self.state = "consolidating"
                print "consolidating"
                self.computeData(tc)
            else:
                self.timeout = tc + 3
        elif self.state == "consolidating":
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
        deviation = self.computeDeviation(intervals, average)
        bpm = int((1 / average) * 60)
        print "Last: %0.2f\tAvg: %0.2f\tDev: %0.2f\tBpm: %d" % (intervals[-1], average, deviation * 50, bpm)
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

    