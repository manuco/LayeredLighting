#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import division

import time, datetime
import math
import sys
import json

from PyQt4.Qt import *


STEPS_BEFORE_COMPUTE = 4
MAX_DEVIATION = 3
MAX_STEPS = 4 * 8

class HumanBeatSensor(QWidget):
    """
        States :
            waiting -> acquring -> learning -> adjusting -> beating -> waiting
    """
    def __init__(self, *args):
        QWidget.__init__(self, *args)
        self.prepareUi()

        self.state = "waiting"
        self.timecodes = []
        self.deviation = 1000
        self.bpm = 0
        self.beatLength = 0
        self.origin = 0
        
        self.beatPerMesure = 4
        self.prepareTimers()

    def prepareUi(self):
        self.beatButton = QPushButton()
        self.beatButton.setText("Beat")
        self.beatButton.setMinimumWidth(200)
        self.beatButton.setMinimumHeight(50)

        self.label = QLabel()
        self.stats = QLabel()
        self.beatLabel = QLabel(" ")

        self.decStepButton = QPushButton()
        self.decStepButton.setText("Beat <")
        self.incStepButton = QPushButton()
        self.incStepButton.setText("Beat >")

        self.decFineStepButton = QPushButton()
        self.decFineStepButton.setText("Adjust <")
        self.incFineStepButton = QPushButton()
        self.incFineStepButton.setText("Adjust >")

        self.decBpmButton = QPushButton()
        self.decBpmButton.setText("BPM -")
        self.incBpmButton = QPushButton()
        self.incBpmButton.setText("BPM +")

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.beatButton)
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.stats)
        self.layout.addWidget(self.beatLabel)

        self.bLayout = QHBoxLayout(self)
        self.bLayout.addWidget(self.decStepButton)
        self.bLayout.addWidget(self.incStepButton)
        self.bLayout.addWidget(self.decFineStepButton)
        self.bLayout.addWidget(self.incFineStepButton)
        self.bLayout.addWidget(self.decBpmButton)
        self.bLayout.addWidget(self.incBpmButton)
        self.layout.addLayout(self.bLayout)

        self.connect(self.decStepButton, SIGNAL("pressed()"), self.decBeat)
        self.connect(self.incStepButton, SIGNAL("pressed()"), self.incBeat)

        self.connect(self.decFineStepButton, SIGNAL("pressed()"), self.decFineAdjust)
        self.connect(self.incFineStepButton, SIGNAL("pressed()"), self.incFineAdjust)


        self.connect(self.decBpmButton, SIGNAL("pressed()"), self.decBpm)
        self.connect(self.incBpmButton, SIGNAL("pressed()"), self.incBpm)

        self.connect(self.beatButton, SIGNAL("pressed()"), self.uiBeatRequested)
        
    def prepareTimers(self):
        self.lightOnTimer = QTimer()
        self.stateTimer = QTimer()
        self.lightOnTimer.setSingleShot(True)
        self.stateTimer.setSingleShot(True)

        self.connect(self.lightOnTimer, SIGNAL("timeout()"), self.uiUpdate)
        self.connect(self.stateTimer, SIGNAL("timeout()"), self.onTimeout)

    def uiUpdate(self):
        tc = time.time()
        beatCount = self.computeBeatCount(tc)

        if self.state == "adjusting" or self.state == "beating":
            nextBeat = self.origin + (beatCount + 1) * self.beatLength
            tmout = int((nextBeat - tc) * 1000)
            self.lightOnTimer.start(tmout)

        self.label.setText(self.state)
        if self.state in ["learning", "adjusting", "beating"]:
            self.stats.setText("Bpm: %0.2f\t\tDev: %0.2f (%d)" % (self.bpm, self.deviation, len(self.timecodes)))
            beat = beatCount % self.beatPerMesure
            beats = "   " * beat + "B" + (self.beatPerMesure - beat - 1) * "   "
            self.beatLabel.setText("%s - %d" % (beats, beat + 1))

        else:
            self.stats.setText("Bpm: --\t\tDev: -- (0)")
            self.beatLabel.setText("Waiting for input")

    def uiBeatRequested(self):
        self.beatRequest()
        self.uiUpdate()


    def decBeat(self):
        self.origin += self.beatLength
        self.commit()

    def incBeat(self):
        self.origin -= self.beatLength
        self.commit()

    def decFineAdjust(self):
        self.origin += self.beatLength / 10
        self.commit()

    def incFineAdjust(self):
        self.origin -= self.beatLength / 10
        self.commit()

    def resetOrigin(self):
        self.origin = self.origin + self.computeBeatCount(time.time()) * self.beatLength

    def decBpm(self):
        self.resetOrigin()
        self.bpm -= 0.1
        self.beatLength = 60 / self.bpm
        self.deviation = 0
        self.timecodes = []
        self.commit()

    def incBpm(self):
        self.resetOrigin()
        self.bpm += 0.1
        self.beatLength = 60 / self.bpm
        self.deviation = 0
        self.timecodes = []
        self.commit()


    def onTimeout(self):
        if self.state == "adjusting":
            self.state = "beating"
            self.commit()
        else:
            self.state = "waiting"
        self.uiUpdate()

    def getTime(self):
        return time.time()

    def updateTimeout(self, length=3):
        self.stateTimer.setInterval(length * 1000)
        self.stateTimer.start()

    def beatRequest(self):
        tc = self.getTime()

        if self.state == "waiting" or self.state == "beating":
            self.timecodes = [tc]
            self.updateTimeout()
            self.state = "acquiring"
        elif self.state == "acquiring":
            self.timecodes += [tc]
            if len(self.timecodes) >= STEPS_BEFORE_COMPUTE:
                self.state = "learning"
                self.computeData(tc)
                self.timecodes = self.timecodes[len(self.timecodes) // 2 :]
            self.updateTimeout()
        elif self.state == "learning":
            self.timecodes += [tc]
            self.computeData(tc)
            if self.deviation < MAX_DEVIATION:
                self.state = "adjusting"
        elif self.state == "adjusting":
            self.timecodes += [tc]
            self.computeData(tc)

        if len(self.timecodes) > MAX_STEPS:
            self.timecodes = self.timecodes[-MAX_STEPS:]

    def computeBeatCount(self, tc):
        try:
            return int((tc - self.origin) / self.beatLength + 0.5)
        except ZeroDivisionError:
            return 0

    def computeIntervals(self):
        t1 = self.timecodes[:-1]
        t2 = self.timecodes[1:]
        return [b - a for a, b in zip(t1, t2)]

    def computeAverage(self, intervals):
        return math.fsum(intervals) / len(intervals)

    def computeDeviation(self, intervals, average):
        return math.sqrt(math.fsum([(v - average) ** 2 for v in intervals]) / len(intervals)) / average

    def computeOrigin(self):
        aggregated_tcs = []
        for i, tc in enumerate(self.timecodes):
            aggregated_tcs.append(tc + self.beatLength * (len(self.timecodes) - 1 - i))

        return self.computeAverage(aggregated_tcs)

    def computeData(self, tc):
        intervals = self.computeIntervals()
        average = self.computeAverage(intervals)
        deviation = self.computeDeviation(intervals, average) * 50
        self.bpm = (1 / average) * 60
        self.deviation = deviation
        self.beatLength = average
        self.origin = self.computeOrigin()
        self.updateTimeout(self.beatLength * 2)

    def timeout(self):
        print "plop"

    def commit(self):
        msg = {
            "request": "beat change",
            "origin": self.origin,
            "beat length": self.beatLength,
        }
        sys.stdout.write(json.dumps(msg) + "\n")

def main():
    app = QApplication(sys.argv)
    pyqtRemoveInputHook()

    hbs = HumanBeatSensor()
    hbs.uiUpdate()

    hbs.show()

    app.exec_()


if "__main__" == __name__:
    main()

    
