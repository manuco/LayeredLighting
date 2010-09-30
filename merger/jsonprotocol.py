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
                    self.stack.pop()
                    if len(self.stack) == 0:
                        docs.append(buffer[self.begin_cur: self.cur + 1])
                        remove_cur = self.cur + 1
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

def zapFirstArg(f):
    def zapFirstArgWorker(a, *arg, **kwargs):
        return f(*arg, **kwargs)
    return zapFirstArgWorker

def protoIn(ch):
    p = JsonProtocol(ch)
    ch.protoIn = zapFirstArg(p.protoIn)
    return ch.protoIn(None)

def protoOut(obj):
    return json.dumps(obj)

    

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

    def test_paquet(self):
        a = """
            {
                "id" : "1",
                "request": "new layer",
                "layer": "1",
                "channels": [
                    {"address": "1", "value": "1"},
                    {"address": "2", "value": "255"},
                    {"address": "3", "value": "127"}
                ]
            }
        """
        ch = ConnectionHandle(None, None)
        jp = JsonProtocol(ch)
        ch.addInData(a)
        r = jp.protoIn()
        self.assertEqual(r, (OK, [eval(a.strip())])
        )


        
if __name__ == "__main__":
    main()    




