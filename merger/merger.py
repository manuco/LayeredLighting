#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys

from communicationmanager import CommunicationManager, allLevelListener
from jsonprotocol import protoIn, protoOut

class Merger(object):
    def __init__(self, com):
        self.com = com
        #com.registerLowLevelListener(allLevelListener)
        com.registerHighLevelListener(allLevelListener)
        com.registerHighLevelListener(self.onEvent)

    def onEvent(self, event):
        pass

def main():
    """Create a default communication manager listening on a unix socket"""
    com = CommunicationManager()
    merger = Merger(com)
    com.listenUnix("/tmp/llmerger", protoIn, protoOut)
    print "ready"
    com.main()

if __name__ == "__main__":
    main()