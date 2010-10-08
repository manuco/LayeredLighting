# -*- coding: utf-8 -*-

jsonClasses = {}

class JSonSerialisableObject(object):

    """
        Attributes that are stored in this object
    """
    attrs = ()

    """
        When loading
        Refs have been requets but not yet received
        Key is the ref uid, value is the attribute name
    """
    pendingRefs = {}

    def register_attrs(self, *name):
        self.attrs += name



def parse(stream):
    """
        Parse JSON data for an object
        Return the (partially) constructed object.

        Remember that you should request uids in the pendingRefs dict
    """
    obj = jsonClasses[stream["kind"]]()
    for attr in stream["attrs"].keys():
        if attr not in obj.attrs:
            raise ValueError("Corrupted object, received attr %s which is not in %s." % (attr, type(obj)))
        setattr(obj, attr, stream["attrs"][attr])
    obj.pendingRefs = stream["refs"]


    return obj

def buildObject(obj, uid, value):
    """
        Fix the object for missing or pending attributes.
        obj is the object to fixed
        uid is the received uid
        value is the stream of the received uid

        return missing uids. [] if the object is completed
    """

    if uid in obj.pendingRef.keys():
        obj = parse_flat(value)
        setattr(obj, obj.pendingRef[uid], obj)
        return obj.pendingRefs.keys()
    else:
        for attr in obj.attrs:
            if attr in obj.pendingRefs.keys():
                continue
            child = getattr(obj, attr)
            if isinstance(child, JSonSerialisableObject):
                try:
                    return buildObject(child, uid, value)
                except ValueError:
                    pass

    raise ValueError("Received UID %s has not been requested." % uid)

def register(kind, class_):
    jsonClasses[kind] = class_


