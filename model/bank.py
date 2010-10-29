#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys, os
sys.path.append(os.path.join(".."))

from common.communicationmanager import CommunicationManager, allLevelListener
from common.jsonprotocol import protoIn, protoOut
from common.communicationmanagerhandler import CommunicationManagerHandler


class Bank(object):
    def __init__(self, name):
        self.name = name
        self.objs = {}

    def __getitem__(self, uid):
        return self.objs[uid]

    def __setitem__(self, uid, obj):
        self.objs[uid] = obj

    def __delitem__(self, uid):
        del self.objs[uid]

    def getNewUid(self):
        return max(self.objs.keys()) + 1

class BankCounter(CommunicationManagerHandler):
    def __init__(self, com=None):
        CommunicationManagerHandler.__init__(self, com)
        self.banks = {}


    def put(self, request, cid, r):
        obj_stream = request["object"]
        bank_id = request["bank"]
        uid = request.get("uid")

        obj = parse(obj_stream)

        bank = self.banks.get(bank_id, Bank(bank_id))
        self.banks[bank_id] = bank

        if uid is None:
            uid = bank.getNewUid()

        bank[uid] = obj
        r["uid"] = uid
        r["status"] = "ok"

    def get(self, request, cid, r):
        bank_id = request["bank"]
        uid = request["uid"]
        bank = self.banks[bank_id]
        r["object"] = bank[uid]
        r["status"] = "ok"

    def delete(self, request, cid, r):
        raise NotImplemented("Bank delete")

    def status(self, request, cid, r):
        r["info"] = "ready"

    def quit(self, request, cid, r):
        self.com.stop()
        r["status"] = "ok"


    request_type = {
        "put": put,
        "get": get,
        "delete": delete,

        "status": status,
        "quit": quit
    }
    



def main():
    com = CommunicationManager()
    bc = BankCounter(com)
    com.listenUnix("/tmp/llbank", protoIn, protoOut)
    print "ready"
    com.main()

if __name__ == "__main__":
    main()
