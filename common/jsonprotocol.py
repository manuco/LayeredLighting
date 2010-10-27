# -*- coding: utf-8 -*-
import json

OK = "OK"
GARBAGE = "GARBAGE"
UNDEFINED = "UNDEFINED"


class JsonProtocol(object):

    delimiters = {
        "{": "}",
        "[": "]",
    }

    def __init__(self):
        self.buffer = ""
        self.cur = 0
        self.stack = []
        self.string = False
        self.begin_cur = 0
    
    def parse(self, data):
        self.buffer += data
        docs = []
        remove_cur = 0
        buffer = self.buffer
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
        
        self.buffer = buffer[remove_cur:]
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

rc = {
    OK: ConnectionHandle.OK,
    GARBAGE: ConnectionHandle.GARBAGE,  
    UNDEFINED: ConnectionHandle.UNDEFINED, 
}

def feedData(p):
    def feedDataWorker(ch):
        r = p.parse(ch.getInData())
        ch.clearInData()
        return (rc[r[0]], r[1])
    return feedDataWorker

def protoIn(ch):
    p = JsonProtocol()
    ch.protoIn = feedData(p)
    return ch.protoIn(ch)

def protoOut(obj):
    return json.dumps(obj) + "\n"

    

from unittest import TestCase
from unittest import main

class JsonProtocolTest(TestCase):

    def test_simple(self):
        jp = JsonProtocol()
        data = "{}"
        r = jp.parse(data)
        self.assertEqual(r, (OK, [{}]))

    def test_two_docs(self):
        jp = JsonProtocol()
        data = "{}[]"
        r = jp.parse(data)
        self.assertEqual(r, (OK, [{}, []]))

    def test_erroneous_1(self):
        jp = JsonProtocol()
        data = "{]"
        r = jp.parse(data)
        self.assertEqual(r, (GARBAGE, []))

    def test_partial(self):
        jp = JsonProtocol()
        data  = "{}["
        r = jp.parse(data)
        self.assertEqual(r, (OK, [{}]))
        data = "]"
        r = jp.parse(data)
        self.assertEqual(r, (OK, [[]]))

    def test_real(self):
        jp = JsonProtocol()
        data = '{"one": 1, "two": 2, "3": "}]}", "5": "bla"} ['
        r = jp.parse(data)
        self.assertEqual(r, (OK, [{"one": 1, "two": 2, "3": "}]}", "5": "bla"}]))
        data = "2, 3, 4]"
        r = jp.parse(data)
        self.assertEqual(r, (OK, [[2, 3, 4]]))

    def test_void(self):
        jp = JsonProtocol()
        r = jp.parse("")
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
        
        jp = JsonProtocol()
        r = jp.parse(a)
        self.assertEqual(r, (OK, [eval(a.strip())])
        )


        
if __name__ == "__main__":
    main()    




