# -*- coding: utf-8 -*-

jsonClasses = {}
jsonKinds = {}

class JSonSerialisableObject(object):

    """
        Attributes that are stored in this object
    """
    attrs = set()

    """
        When loading
        Refs have been requets but not yet received
        Key is the ref uid, value is the attribute name
    """
    pendingRefs = {}

    def register_attrs(self, *name):
        self.attrs = set(self.attrs)
        self.attrs |= set(name)

def parse(stream):
    """
        Parse JSON data for an object
        Return the (partially) constructed object.

        Remember that you should request uids in the pendingRefs dict
    """
    obj = jsonClasses[stream["kind"]]()

    attrsInStreams = set()
    try:
        attrsInStreams |= set(stream["attrs"].keys())
    except KeyError:
        pass
    try:
        attrsInStreams |= set(stream["refs"].values())
    except KeyError:
        pass

    if attrsInStreams != obj.attrs:
        print obj.attrs
        print attrsInStreams
        raise ValueError("Corrupted object, stream attrs %s  are not object attrs %s." % (tuple(attrsInStreams), tuple(obj.attrs)))

    try:
        for attr in stream["attrs"].keys():
            setattr(obj, attr, stream["attrs"][attr])
    except KeyError:
        pass

    try:
        obj.pendingRefs = stream["refs"]
    except KeyError:
        pass
    
    return obj

def buildObject(obj, stream):
    """
        Fix the object for missing or pending attributes.
        obj is the object to fixed, None to build a new
        stream is the data to fixe or create the object

        return the object and next missing uids (or [] if the object is ready)
    """

    if obj is None:
        obj = parse(stream)
        return obj, obj.pendingRefs.keys() if hasattr(obj, "pendingRefs") else []

    uid = stream["uid"]

    unfinishedAttrs = [attr for attr in obj.pendingRefs.values() if hasattr(obj, attr)]
    missingAttrs = [attr for attr in obj.pendingRefs.values() if not hasattr(obj, attr)]
    missingUids = [uid for uid in obj.pendingRefs.keys() if obj.pendingRefs[uid] in missingAttrs]

    nextMissing = []

    if uid in missingUids:
        subObj = parse(stream)
        setattr(obj, obj.pendingRefs[uid], subObj)
        if not hasattr(subObj, "pendingRefs"):
            # subObj is complete
            del obj.pendingRefs[uid]
        else:
            nextMissing += subObj.pendingRefs.keys()
        missingUids.remove(uid)
    else:
        for attr in unfinishedAttrs:
            subObj = getattr(obj, attr)
            subObj, missing = buildObject(subObj, stream)
            if len(missing):
                nextMissing += missing
            else:
                # subObj is complete
                del obj.pendingRefs[uid]

    if len(obj.pendingRefs) == 0:
        del obj.pendingRefs

    return obj, nextMissing + missingUids

def serialize(obj, uid):
    """
        uid : the uid of this object
        Return a list tuple of stream (as dict)
    """
    streams = []

    stream = {
        "uid": uid,
        "kind": jsonKinds[type(obj)]
    }
    refs = {}
    attrs = {}
    for attr in obj.attrs:
        subElem = getattr(obj, attr)
        if isinstance(subElem, JSonSerialisableObject):
            nuid = uid + "." + attr
            streams += serialize(subElem, nuid)
            refs[nuid] = attr
        else:
            attrs[attr] = subElem
    if len(refs) > 0:
        stream["refs"] = refs
    if len(attrs) > 0:
        stream["attrs"] = attrs
    streams.append(stream)
    return streams



def register(kind, class_):
    jsonClasses[kind] = class_
    jsonKinds[class_] = kind


