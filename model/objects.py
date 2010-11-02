# -*- coding: utf-8 -*-
import sys, os
sys.path.append(os.path.join(".."))

class ChannelInfo(object):
    """
        channels are channels holding the value, typically only
        one channel, but in case of 16bits value, multiple
        channels can be involved

        value is the DMX value for this or these channels.

        mix is either "min", "max", or 0 (only down value) -> 1 (only our value) float
            will be used by the merger
    """
    def __init__(self):
        self._channels = []
        self._value = 0
        self._mix = 1

class Length(object):
    """
        A length in :
            - milliseconds
            - bars (measures)
            - beats

        value is an integer holding the value
        type is either "millis", "bars" or "beats"
    """
    def __init__(self):
        self._value = 0
        self._type = "millis"

class Effect(object):
    """
        An effect that return a multiplier given a timing,
        parameters, and an arbitrary function

        script is the script that will contain the function
        computing the desired value
        function_name is the name of the function in the script
        that will be executed
        params is a list of live params
    """

    def __init__(self):
        self._script = ""
        self._function_name
        self._params = {}

class Scene(object):
    """
        Channels info are all the channels, and their values that will
        be hold by this scene

        Length is the default lenght for this scene, if any is needed (when not in sequence), if None, scene has no limit
        Fade in length is the length the scene will take to be fully set (when not in sequence)
        Fade out length is the length the scene will take to be shut down (when not is sequence)
        Fade in type is the type of fade in (linear, cubic, ...)
        Fade out type is the type of fade out (linear, cubic, ...)
        Fade affected channels are channels that will see their values affected by fade in and out (index in the channels info list)
        Effect affected channels are channels that will see their values affected effect object, if any (index in the channels info list)
        Effect is an Effect object, that will return a multiplier that will affect some channels

        Scene is a playable element : it will returns channels values when given some timecode infos
    """

    def __init__(self):
        self._channels_info = []
        self._length = None
        self._length_fade_in = None
        self._length_fade_out = None
        self._type_fade_in = None
        self._type_fade_out = None
        self._fade_affected_channels = set()
        self._effect_affected_channels = set()
        self._effect = None

class Step(object):
    """
        A step is a scene in a sequence. Some values defined here ovveride those
        defined in the scene.

        Playable is a reference to the scene in this step, or any playable elems
        Length is the length of this step, excluding any fades
        Transition length is the length of the transition with the next step
    """

    def __init__(self):
        self._playable = None
        self._length = None
        self._transition_length = None

class Sequence(object):
    """
        A sequence is a succession of steps holding scenes.

        Steps are in forward order
        Loop count is the number of loop the sequence should do, 0 is infinite.
        Total length is used when loop count is 0. In any case total length is enforced, should the sequence be longer
        Step event is the event that will produce transition and the next step

        Sequence is a playable element : it will returns channels values when given some timecode infos
    """

    def __init__(self):
        self._steps = []
        self._loop_count = 0
        self._total_length = None
        self._step_event = None

class MultiSequencePlayable(object):
    """
        A multi sequence playable embed any playable (multisequence, sequence or scene)

        Playable is a reference to a playable.
        Begin is the length to wait before playing this.
        Origin is the origin of the begin length
        Line is the position in the ms where we are. Collision must not happen, and should be checked.
    """

    def __init__(self):
        self._playable = None
        self._begin = None
        self._origin = None
        self._line = 0

class MultiSequence(object):
    """
        A multi sequence is the core of the model. It holds refs to all others
        playables. MultiSequence can contains other MultiSequences, Sequences and Scenes.
        Each playable is on a virtual line. The line number will determine the layer on
        the output.
    """
    def __init__(self):
        # XXX should storage be more efficient ?
        self._ms_playables = []

        