#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import re

from collections import defaultdict

from communicationmanager import CommunicationManager, allLevelListener
from jsonprotocol import protoIn, protoOut

class Channel(object):
    """
        A channel is a feature channel. It describe DMX channels on
        8 or 16 bits (or more...)
        
        It contains 
        - the value for this channel
        - the DMX channel count needed to encode the value
            (think about fine pan/tilt for moving heads)
        - the mixtype : 
            - a float between 0.0 and 1.0 that will be used to mix this channel value
            with the lower one
            - "min": the min between this value and the lower one
            - "max": the max between this value and the lower one
            If this channel is the lowest one, the mixtype is not used
            (defaults to 1.0).
    """
    def __init__(self, value, mixType, nbChan):
        self.value = value
        self.nbChan = nbChan
        self.mixType = mixType

class Layer(object):
    """
        A layer is a set of channels that interract with channels of lower
        layers.
        
        Layers are used by the merger to compute the DMX values for the DMX Galaxy.
        
        Layers have a level, which orders them. Levels are in dotted notation :
         2 > 1
         2.1 > 2
         2.1 > 1
         1.1 > 1
         1.1.1 > 1.1
         -1 > 99
         -2 > -1
    """

    def _checkLevel(self, level):
        regexp = r"^-?\d+(\.-?\d+)*$"
        if not re.match(regexp, level):
            raise ValueError("Bad level format")

    def __lt__(self, other):
        left = self.level.split(".")
        right = other.level.split(".")

        i = 0
        while True:
            if i == len(left):
                return True
            if i == len(right):
                return False

            l = int(left[i])
            r = int(right[i])

            if (l > 0 and r > 0) or (l < 0 and r < 0):
                l = abs(l)
                r = abs(r)
                if l < r:
                    return True

                if l > r:
                    return False

            if l < 0 and r > 0:
                return False

            if l > 0 and r < 0:
                return True
            i += 1

    def __init__(self, level):
        self._checkLevel(level)
        self.level = level

        self.channels = {}


    def addChannel(self, address, value, mixType=1.0, nbChan=1):
        """
            Add channel values to this layer
            @param address: the channel address. Channels are replaced if they already exist.
            @param value: the value of this channel
            @param mixType: how to compute the layer's value with the under one
                values can be :
                    - a float between 0 and 1, 0 is the complete value of the under layer
                                               1 is the complete value of this layer
                    - "min", the min between this layer and the under one
                    - "max", the max between the two layers
        """
        self.channels[address] = Channel(value, mixType, nbChan)


    def updateChannel(self, address, value=None, mixType=None):
        """
            Update channel value or mixType (or both)
        """
        if value is not None:
            self.channels[address].value = value
        if mixType is not None:
            self.channels[address].mixType = mixType

    def delChannel(self, address):
        del self.channels[address]

class Merger(object):
    """
        A merger takes a set of layers and generate a DMX galaxy based on channel
        values placed in channels.
        
        Most operations are available as commands sent on a unix socket. 
    """
    def __init__(self, com=None):
        if com:
            self.setComManager(com)
        self.layers = []
        self.galaxy = DMXGalaxy()

    def setComManager(self, com):
        self.com = com
        com.registerHighLevelListener(allLevelListener)
        com.registerHighLevelListener(self.onEvent)

    def onEvent(self, event):
        if event[0] == "packet":
            r = self.handleRequest(event[2], event[1])
            self.com.send(event[1], r)
            self.merge()
        elif event[0] == "connection closed":
            self.handleClosedConnection(event[1])

    def handleClosedConnection(self, cid):
        layers_to_remove = []
        for layer in self.layers:
            if layer.status != "persistent" and layer.cid == cid:
                layers_to_remove.append(layer)

        map(self.delLayer, layers_to_remove)

    def handleRequest(self, request, cid):

        request_type = {
            "new layer": self.newLayer,
            "remove layer": self.removeLayer,

            "new channels": self.newChannel,
            "remove channels": self.removeChannel,
            "update channels": self.updateChannel,

            "status": self.status,
            "output": self.output,
            "quit": self.quit
        }
        try:
            rid = request["id"]
        except (KeyError, TypeError):
            return {"error": "Protocol error, missing request id"}

        try:
            r = {"id": rid}
            request_type[request["request"]](request, cid, r)
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
        return r


    def newLayer(self, request, cid, r):
        """
            Handle a new layer request
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
        l = Layer(request["layer"])
        l.status = request.get("status", "volatile") # or pesistent
        l.cid = cid
        self.addLayer(l)
        r["status"] = "ok"
        self.newChannel(request, cid, r)

    def removeLayer(self, request, cid, r):
        self.delLayer(request["layer"])
        r["status"] = "ok"

    def newChannel(self, request, cid, r):
        l = self.getLayer(request["layer"])
        channels = request.get("channels", [])
        for channel in channels:
            address = int(channel["address"])
            try:
                mixType = float(channel.get("mixType", 1.0))
            except ValueError:
                mixType = channel["mixType"]
            nbChan = int(channel.get("nbChan", 1))
            value = int(channel["value"]) & (256 * nbChan - 1)
            l.addChannel(address, value, mixType, nbChan)

    def updateChannel(self, request, cid, r):
        l = self.getLayer(request["layer"])
        channels = request.get("channels", [])
        for channel in channels:
            address = int(channel["address"])
            mixType = None if not channel.has_key("mixType") else float(channel.get("mixType", 1.0))
            value = None if not channel.has_key("value") else int(channel["value"]) & (256 * nbChan - 1)
            l.updateChannel(address, value, mixType)

    def removeChannel(self, request, cid, r):
        l = self.getLayer(request["layer"])
        channels = request.get("channels", [])
        for channel in channels:
            address = int(channel["address"])
            l.delChannel(address)


    def addLayer(self, layer):
        self.delLayer(layer.level)
        self.layers.append(layer)

    def getLayer(self, level):
        for layer in self.layers:
            if layer.level == level:
                return layer
        raise ValueError("Unknow layer: %s" % level)
            

    def delLayer(self, layer):
        if type(layer) not in (type(""), type(u"")):
            layer = layer.level
        for layer_l in self.layers:
            if layer == layer_l.level:
                self.layers.remove(layer_l)
                break

    def merge(self):
        self.galaxy.clear()
        self.layers.sort()

        for layer in self.layers:
            for item in layer.channels.items():
                self.merge_channel(*item)

        self.updateUnivers()

    def merge_channel(self, address, channel):
        old_value = 0
        for i in range(channel.nbChan):
            old_value = (old_value << 8) + self.galaxy[address + i]
        value = self.mix_channel(old_value, channel)
        for i in range(channel.nbChan):
            self.galaxy[address + (channel.nbChan - i - 1)] = value & 255
            value >>= 8

    def mix_channel(self, value, channel):
        if type(channel.mixType) == type(1.0):
            return int((1 - channel.mixType) * value + channel.mixType * channel.value + 0.5)
        if channel.mixType == "min":
            return min(value, channel.value)
        if channel.mixType == "max":
            return max(value, channel.value)

        raise ValueError("%s: Unknow mix type" % channel.mixType)


    def updateUnivers(self):
        pass

    def status(self, request, cid, r):
        layers = {}
        for layer in self.layers:
            l = {}
            for address, channel in layer.channels.items():
                l[address] = {
                    "value": channel.value,
                    "mixType": channel.mixType,
                    "nbChan": channel.nbChan,
                }
            layers[layer.level] = l
        r["data"] = {"layers" : layers}

    def output(self, request, cid, r):
        r["output"] = self.galaxy


    def quit(self, request, cid, r):
        self.com.stop()
        r["status"] = "ok"

class DMXGalaxy(defaultdict):
    def __init__(self):
        defaultdict.__init__(self, lambda:0)


def main():
    """Create a default communication manager listening on a unix socket"""
    com = CommunicationManager()
    merger = Merger(com)
    com.listenUnix("/tmp/llmerger", protoIn, protoOut)
    print "ready"
    com.main()

if __name__ == "__main__":
    main()



    
