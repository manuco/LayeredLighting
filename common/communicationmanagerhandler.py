# -*- coding: utf-8 -*-

from common.communicationmanager import allLevelListener

class CommunicationManagerHandler(object):
    def __init__(self, com):
        if com:
            self.setComManager(com)

    def setComManager(self, com):
        self.com = com
        com.registerHighLevelListener(allLevelListener)
        com.registerHighLevelListener(self.onEvent)

    def onEvent(self, event):
        if event[0] == "packet":
            r = self.handleRequest(event[2], event[1])
            self.com.send(event[1], r)

    def handleRequest(self, request, cid):
        try:
            rid = request["id"]
        except (KeyError, TypeError):
            return {"error": "Protocol error, missing request id"}

        try:
            r = {"id": rid}
            self.request_type[request["request"]](self, request, cid, r)
        except KeyError, e:
            return {
                "id": rid,
                "error": "Protocol error, missing key: %s" % e.args[0],
            }
        except ValueError, e:
            return {
                "id": rid,
                "error": "Value error: %s" % e.args[0],
            }
        except Exception, e:
            return {
                "id": rid,
                "error": "Exception: %s %s" % (e, e.args[0]),
            }

        return r


