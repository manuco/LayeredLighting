# -*- coding: utf-8 -*-

class BankAccess(object):
    def __init__(self):
        self.pendingUids = {}
        pass

    def get(self, uid):
        
        