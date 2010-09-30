# -*- coding: utf-8 -*-
import json

from communicationmanager import ConnectionHandle
OK = ConnectionHandle.OK
GARBAGE = ConnectionHandle.GARBAGE
UNDEFINED = ConnectionHandle.UNDEFINED


class JsonProtocol(object):

    delimiters = {
        "{": "}",
        "[": "]",
    }

    def __init__(self, ch):
        self.ch = ch
        self.cur = 0
        self.stack = []
        self.string = False
        self.begin_cur = 0
        
    def protoIn(self):
        docs = []
        remove_cur = 0
        buffer = self.ch.getInData()
        max_cur = len(buffer)
        while self.cur < max_cur:
            char = buffer[self.cur]
            if self.string:
                if char == '\\':
                    self.cur += 1
                elif char == '"':
                    self.string = False
            else:
                if char in self.delimiters.keys():
                    if len(self.stack) == 0:
                        self.begin_cur = self.cur
                    self.stack.append(char)
                elif char in self.delimiters.values():
                    try:
                        if char != self.delimiters[self.stack[-1]]:
                            return GARBAGE, []
                    except IndexError:
                        return GARBAGE, []
                    docs.append(buffer[self.begin_cur: self.cur + 1])
                    remove_cur = self.cur + 1
                    self.stack.pop()
                elif char == '"':
                    self.string = True
            self.cur += 1
        
        self.ch.clearInData(remove_cur)
        self.begin_cur -= remove_cur
        self.cur -= remove_cur
        r = []
        if len(docs):
            try:
                for doc in docs:
                    r.append(json.loads(doc))
            except ValueError:
                return GARBAGE, []
            return OK, r
        return UNDEFINED, []
    
    def protoOut(self, objs):
        r = ""
        for obj in objs:
            r += json.dumps(obj)
        return r
    
def zapFirstArg(f):
    def zapFirstArgWorker(a, *arg, **kwargs):
        return f(*arg, **kwargs)
    return zapFirstArgWorker

def installProtoHandler(ch):
    p = JsonProtocol(ch)
    ch.protoIn = zapFirstArg(p.protoIn)
    ch.protoOut = zapFirstArg(p.protoOut)

def protoIn(ch):
    installProtoHandler(ch)
    return ch.protoIn(None)

def protoOut(ch):
    installProtoHandler(ch)
    return ch.protoOut(None)


from unittest import TestCase
from unittest import main

class JsonProtocolTest(TestCase):

    def test_simple(self):
        ch = ConnectionHandle(None, None)
        jp = JsonProtocol(ch)
        ch.addInData("{}")
        r = jp.protoIn()
        self.assertEqual(r, (OK, [{}]))

    def test_two_docs(self):
        ch = ConnectionHandle(None, None)
        jp = JsonProtocol(ch)
        ch.addInData("{}[]")
        r = jp.protoIn()
        self.assertEqual(r, (OK, [{}, []]))

    def test_erroneous_1(self):
        ch = ConnectionHandle(None, None)
        jp = JsonProtocol(ch)
        ch.addInData("{]")
        r = jp.protoIn()
        self.assertEqual(r, (GARBAGE, []))

    def test_partial(self):
        ch = ConnectionHandle(None, None)
        jp = JsonProtocol(ch)
        ch.addInData("{}[")
        r = jp.protoIn()
        self.assertEqual(r, (OK, [{}]))
        ch.addInData("]")
        r = jp.protoIn()
        self.assertEqual(r, (OK, [[]]))

    def test_real(self):
        ch = ConnectionHandle(None, None)
        jp = JsonProtocol(ch)
        ch.addInData('{"one": 1, "two": 2, "3": "}]}", "5": "bla"} [')
        r = jp.protoIn()
        self.assertEqual(r, (OK, [{"one": 1, "two": 2, "3": "}]}", "5": "bla"}]))
        ch.addInData("2, 3, 4]")
        r = jp.protoIn()
        self.assertEqual(r, (OK, [[2, 3, 4]]))

    def test_void(self):
        ch = ConnectionHandle(None, None)
        jp = JsonProtocol(ch)
        ch.addInData("")
        r = jp.protoIn()
        self.assertEqual(r, (UNDEFINED, []))

        
if __name__ == "__main__":
    main()    




