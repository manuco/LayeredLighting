#!/usr/bin/env python
"""
    CommunicationManager module is a module wrapping the select / poll system calls
    enabling you to have a single (or double if you adopt the non blocking mode)
    threaded multiple IO management.
    
    Via the CommunicationManager class, you will add and remove IO streams (mainly
    socket, even if pipes and files also work) to the manager. This one will
    dispatch your data and alerts you via callbacks when something is received.
    
    Usage (non blocking):
    
        >>> ## Creating it
        >>> com = CommunicationManager(blocking = False)
        >>> com.registerLowLevelListener(allLevelListener)
        >>> com.registerHighLevelListener(allLevelListener)
        >>> 
        >>> ## Enable it to listen on one port
        >>> lsid = com.listen(port=5555)
        >>> 
        >>> ## Connect to another place
        >>> csid = com.connect("ip6-localhost", 5555)
        >>> 
        >>> ## send something
        >>> com.sendRaw(csid, "some data")
        >>> 
        >>> ## add some File Descriptors
        >>> (pin, pout) = os.pipe()
        >>> com.addFDescriptor(pout)
        >>> com.sendRaw(pout, "plop 1")
        >>> print "----->", os.read(pin, 255) ## "plop 1" 
        >>> com.removeFDescriptor(pout)
        >>> 
        >>>     ## Stop and close everything
        >>> com.stop()

    Usage (blocking):
    
        >>> ## Creating it
        >>> com = CommunicationManager()
        >>> com.registerLowLevelListener(allLevelListener)
        >>> com.registerHighLevelListener(allLevelListener)
        >>> 
        >>> ## Enable it to listen on one port
        >>> lsid = com.listen(port=5555)
        >>> 
        >>> ## Connect to another place
        >>> csid = com.connect("ip6-localhost", 5555)
        >>> 
        >>> ## Let's enter the main loop
        >>> com.main()
        >>> 
        >>> ## Stop and close everything (in a callback since main is blocking)
        >>> com.stop()

    @author: Emmanuel Coirier
    @copyright: 2005-2010 Emmanuel Coirier
    @license: GPL v3
"""

import threading
import select
import socket
import time
import os
import os.path
import sys
import errno
import bdb

import pprint

class ConnectionHandle(object):
    """
        The Connection Handle contains the IO buffers of the associated socket.
        For inputs, it stores all data until a complete protocol packet is receive
        For outputs, it stores all data until the socket is ready to send.
        
        This class in only needed for the default communication manager, 
        the Qt ones has it's own mechanism.        
        
        Operations on buffers run as FIFO.
    """
    def __init__(self, cm, socket, protoIn=None, protoOut=None, ssl=False):
        """
            Create a new Connection Handle. The specific protocol callback will
            be used instead of the CommunicationManager ones if they are set.
            
            @param cm: an instance of a CommunicationManager
            @param socket: the associated socket
            @param protoIn: specific protocol callback (see CommunicationManager.__init__ doc)
            @param protoOut: specific protocol callback (see CommunicationManager.__init__ doc)
            @param ssl: enable ssl if True
        """
        self.cm = cm
        self.socket = socket
        self.isInPollList = False
        # We must poll for something, else the connection will be considered finished
        self.pollFor = select.POLLIN
        self.listening = False
        self.connecting = False
        self.dontClose = False # set it to true if the socket should live after a disconnection. It won't be managed anymore by the connection manager.
        self.inData = ""
        self.outData = ""
        self.protoIn = protoIn
        self.protoOut = protoOut
        self.semaOut = threading.Semaphore()
        self.ssl = ssl
        self.hold = False
        self.readUntil = 0

    def getOutData(self):
        """
            @return: a copy of all data in the out buffer. Data has not been
            sent and is not cleared at the end of the call.
            
            Thread-safe.
        """
        self.semaOut.acquire()
        data = str(self.outData)
        self.semaOut.release()
        return data

    def removeOutData(self, howMany):
        """
            Clear part of the out buffer. If no more data is present, the pollout
            flag is removed.
            
            Thread-safe.

            @param howMany: how many bytes to remove from the beginning of the buffer
        """
    
        self.semaOut.acquire()
        self.outData = self.outData[howMany:]
        if len(self.outData) == 0 :
            self.pollFor &= ~select.POLLOUT
        self.semaOut.release()

    def addOutData(self, data):
        """
            Add some data at the end of the out buffer. The pollout flag is set.
            If the socket is ready, data is immediatly sent at the next loop turn.
            
            Thread-safe
            
            @param data: a string of bytes
            @return: the number of bytes in the buffer
        """
        self.semaOut.acquire()
        self.pollFor |= select.POLLOUT
        self.outData += data
        result = len(self.outData)
        self.semaOut.release()
        self.cm._wakeup("Alerts poll that new data are ready to be sent on socket %d" % self.sid())
        return result


    ## No synchro is needed for inputData since we are the only one to access this object
    def getInData(self):
        """
            Get input data. Data stays in the buffer.
        """
        return self.inData

    def clearInData(self, howMany=None):
        """
            Clear input buffer. Used by protoIn callback.
            @param howMany: How many bytes to remove. Default to None which means
            all data.
        """
        if howMany == None:
            self.inData = ""
        else :
            self.inData = self.inData[howMany:]

    def addInData(self, data):
        """
            Add data which has just be read. Only used by CommunicationManager.
        """
        self.inData += data

    def sid(self):
        """
            @return: the socket id. 
            @note: this is the file descriptor.
        """
        try:
            return self.socket.fileno()
        except AttributeError:
            ## in case the socket is in fact a fd...
            return self.socket

    def enableSSL(self, serverSide):
        """
            Enable the ssl wrapper around this socket
            @param serverMode: True is this socket is a server socket
        """
        import ssl
        
        self.socket = ssl.wrap_socket(
            self.socket,
            server_side=serverSide,
            certfile=self.ssl if type(self.ssl) == type("") else None,
        )
        self.ssl = "server" if serverSide else "client"

    def disableSSL(self):
        """
            Disable the ssl wrapper.
        """
        self.socket = self.socket.unwrap()
        self.ssl = False

    GARBAGE = 0
    """ Stream is corrupted or doesn't contain any valid data. The stream will be
    flushed by the system """
    OK = 1 ## Packet has been read succesfully
    """ Stream format is ok """
    UNDEFINED = 2 ## undefined
    """ Stream format is ok, but nothing has to be reported """


class CommunicationManager(object):
    """
        Manage communication between differents parts of processes, via IO. 
        
        The communication manager is responsible for communication between 
        different processes, via sockets or other IO devices. It will emit various
        events given what data is received on the created sockets.
        
        The manager can be used in two modes:
          - blocking: in this case, once created, you should call the main
            method in order to enable it to work. Or you can call the loop
            method repeteadly until it return false. In either case, these
            methods will block. 
            
          - non blocking: you have nothing to do: once constructed, the
            communication manager will do its work. 
        
        In order to interact with the communication manager, you have to
        register some callback functions for the various emmited events.
        
        Low level events are events focused on inputs and outputs operations.
        You won't need most of them since they are only usefull for debugging
        purposes. Included are low-level TCP connection process like "CONNECTING",
        "CONNECTION CLOSED", and detailed errors.
        
        High level events are more application level events. They notify you
        for packets received formated by the protoIn callback (see below).
        
        Moreover, you should provide a "protoIn" callback used for parsing the
        stream looking for higher level messages, and a "protoOut" callback that
        will receive these messages that have to be serialized to be carried by
        the stream. For example, if you use Json/Yaml messages, you can cut the
        stream based on various bounds and call the yaml/json parser.
        Respectively, you will call the json/yaml formatter for your high level
        messages.
    """
    
    def __init__(self, blocking=True, protoIn=None, protoOut=None):
        """
            Create a communication manager.
            
            @param blocking: a boolean indicating if the Communication Manager
            should be running on its own thread (False), or if it will be called
            via its main function (True)
            
            @param protoIn: a callback which will cuts the stream
            into packets. It take one parameter which will be an instance of
            ConnectionHandle, and should return a tuple of two values:
                - the constant OK, GARBAGE or UNDEFINED (see their docstrings)
                - a list of messages, that will be thrown as high events (one event
                  per message). 
            This callback has to manage the in buffer of the connection handle
            itself. It won't be clear until you do.
            Default is a callback where each packet is the bytes received at
            the last read call as a string.
            
            @param protoOut: a callback wich will format a list of packet into
            a string. It take one parameter : a list of packet to send and return
            one string with the value converted.
            Default is a callback calling str() on each object, concatenating them.
            
        """
    
        self.lowLevelListeners = []
        self.highLevelListeners = []
        self.semaChs = threading.Semaphore()
        self.semaChs.acquire()
        self.chs = {}
        self.stopOnExceptionFlag = False
        self.stopOnKeyboardInterruptFlag = True
        self.poll = select.poll()
        self.running = True
        self.connectionCount = 0
        self.wakeupPipe = os.pipe()
        self.timeouts = TimeoutsManagement()
        self.poll.register(self.wakeupPipe[0], select.POLLIN)
        if protoIn:
            self.protoIn = protoIn
        else:
            self.protoIn = returnRaw
            
        if protoOut:
            self.protoOut = protoOut
        else:
            self.protoOut = returnIdentity

        if not blocking :
            self.comThread = threading.Thread(target = self.main)
            self.comThread.start()
        self.semaChs.release()

    def _wakeup(self, reason):
        """
            Wake up select in case we have work.
            @param reason: Whe should we wake-up? This is a string used only for
            debug.
        """
        self._throwLowLevelEvent((self.wakeupPipe[1], "WAKE UP", reason))
        os.write(self.wakeupPipe[1], "!") ## put anything in the pipe to wake up the poll call.

    def _managePollList(self):
        """
            Manage all the connections in the polling object. 
            If an object polls for nothing, it is removed. 
        """
        chToRelease = []
        self.semaChs.acquire()
        for ch in self.chs.values():
            if ch.pollFor == 0:
                if ch.isInPollList:
                    self.poll.unregister(ch.socket)
                    ch.isInPollList = False
                if not ch.hold:
                    chToRelease.append(ch)

            if ch.pollFor != 0:
                self.poll.register(ch.socket, ch.pollFor)
                ch.isInPollList = True
        self.semaChs.release()
        for ch in chToRelease:
            self._releaseSocket(ch)

    def _releaseSocket(self, ch) :
        """
            Remove a socket from the ConnectionManager. After then, there is
            no more trace of it here.
        """
        self.semaChs.acquire()
        del self.chs[ch.sid()]
        self.semaChs.release()
        if ch.dontClose:
            self._throwLowLevelEvent((ch.sid(), "FD REMOVED"))
            self._throwHighLevelEvent(("file descriptor unmanaged", ch.sid()))
        else:
            sid = ch.sid()
            try:
                if ch.listening and type("") == type(ch.socket.getsockname()) and os.path.exists(ch.socket.getsockname()):
                    os.unlink(ch.socket.getsockname())

                ch.socket.close()

            except AttributeError:
                ## socket is a FD
                os.close(ch.socket)
                
            self._throwLowLevelEvent((sid, "CONNECTION CLOSED"))
            self._throwHighLevelEvent(("connection closed", sid))

        self.connectionCount -= 1


    def _manageInData(self, ch):
        """
            Manage incoming data. Throws events.
        """
        if ch.protoIn is not None:
            result, packetList = ch.protoIn(ch)
        else:
            result, packetList = self.protoIn(ch)
        if result == ch.GARBAGE:
            self._throwHighLevelEvent(("protocol error", ch.sid(), "packet malformed (%s)" % packetList))
            ch.clearInData()
        elif result == ch.OK:
            for packet in packetList :
                self._throwHighLevelEvent(("packet", ch.sid(), packet))

    def _readSocket(self, ch):
        """
            Try reading socket. Close it properly if
            needed.
        """
        sizeToRead = ch.readUntil if ch.readUntil != 0 else 4096 
        try:
            if ch.ssl:
                data = ""
                data += ch.socket.read(sizeToRead)
                try:
                    while len(data) != 0:
                        data += ch.socket.read(sizeToRead)
                except socket.error, error:
                    if error[0] != errno.ENOENT: #EWOULDBLOCK
                        raise
            else:
                data = ch.socket.recv(sizeToRead)
        except socket.error, error:
            self._manageErroneousConnection(ch, error[0])
            return
        except AttributeError:
            ## socket is a fd
            try:
                data = os.read(ch.socket, sizeToRead)
            except OSError, e:
                if e[0] == errno.EBADF: # Bad file descriptor
                    # Bad File descriptor ?
                    # When a fd is write only, POLLIN is kept up by the system...
                    # so hold the fd in order to not wait for POLLIN events...
                    self.hold(ch.socket)
                    return
                else:
                    raise
            except IOError, e:
                self.manageErroneousConnection(ch, e)
                
        if ch.readUntil != 0 and len(data) == ch.readUntil and not ch.ssl:
            self.hold(ch.sid())

        if data == "" : ## socket has been properly closed
            ch.pollFor &= ~select.POLLIN ## nothing more to read.
        else :
            self._throwLowLevelEvent((ch.sid(), "READ", str(data)))
            ch.addInData(data)
            self._manageInData(ch)

    def _writeSocket(self, ch):
        """
            Try writing the socket.
        """
        data = ch.getOutData()
        try:
            if ch.ssl:
                sentLen = ch.socket.write(data)
            else:
                sentLen = ch.socket.send(data)
        except AttributeError:
            ## socket is a FD
            sentLen = os.write(ch.socket, data)
        ch.removeOutData(sentLen)
        self._throwLowLevelEvent((ch.sid(), "WRITE", str(data[:sentLen])))

    def send(self, cid, data):
        """
            Send some data over the network.
            @parameter cid: the connection id
            @parameter data: the data to send, will be converted with protoOut callback
            @return: the number of bytes in the out buffer
        """
        ch = self._cidToCh(cid)
        protoOut = self.protoOut if ch.protoOut is None else ch.protoOut
        return self.sendRaw(cid, protoOut(data))

    def sendRaw(self, cid, data):
        """
            Send bytes on the wire. In fact, only add data in the out buffer.
            @return: the number of bytes in the out buffer
        """
        ch = self._cidToCh(cid)
        return ch.addOutData(data)

    def _createConnectedSocket(self, ch):
        """
            Given a connection handle which should have a pending connection,
            create a new socket.
            
            Called when someone is connecting to us.
            
            @param ch: the listening connection handle
        """
        self.connectionCount += 1
        # returns (socket, address)
        connection = ch.socket.accept()
        nch = ConnectionHandle(self, socket=connection[0], protoIn=ch.protoIn, protoOut=ch.protoOut, ssl=ch.ssl) 
        nch.socket.setblocking(False)
        self.chs[nch.sid()] = nch
        self._throwLowLevelEvent((nch.sid(), "NEW CONNECTION", connection[1], nch.socket.getsockname()))
        self._throwHighLevelEvent(("incoming connection", nch.sid()))
        # we are now ready to accept incoming data
        nch.pollFor |= select.POLLIN
        if ch.ssl:
            try:
                nch.enableSSL(serverSide=True)
            except socket.error, error:
                nch.ssl = False
                self._manageErroneousConnection(ch, error[0])
                return
            except:
                ch.ssl = False
                ch.pollFor = 0
                raise


    def _completeConnectedSocket(self, ch):
        """
            An outcoming connection to another peer is completed. Do the final work.
        """
        ch.pollFor |= select.POLLIN
        ## POLLOUT was needed for connection completion, so it is already set
        if len(ch.getOutData()) == 0:
            ch.pollFor &= ~select.POLLOUT
        if ch.ssl:
            try:
                ch.enableSSL(serverSide=False)
            except socket.error, error:
                ch.ssl = False
                self._manageErroneousConnection(ch, error[0])
                return
            except:
                ch.ssl = False
                ch.pollFor = 0
                raise

        ch.connecting = False
        self._throwLowLevelEvent((ch.sid(), "CONNECTED", ch.socket.getpeername(), ch.socket.getsockname()))
        self._throwHighLevelEvent(("outcoming connection", ch.sid()))


    def _manageErroneousConnection(self, ch, error=None):
        """
            This connection return us an error. Try to manage it.
        """
        if ch.pollFor == 0: # already managed
            return
        if error == None:
            error = ch.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        if error != 0:
            self._throwLowLevelEvent((ch.sid(), "ERROR", error, errno.errorcode[error], os.strerror(error)))
            self._throwHighLevelEvent(("connection error", ch.sid(), os.strerror(error)))
        else:
            ## we should never be here...
            print >>sys.stderr, "Error : POLLERR and no error."
            raise RuntimeError("Error : POLLERR and no error.")
        ## we ask the connection to be closed and forgotten
        ch.pollFor = 0

    def _managePollReturn(self, descs):
        """
            Analyze what poll tries to explain us...
        """        
        for desc, event in descs :
            if desc == self.wakeupPipe[0]: ## flush the pipe
                self._throwLowLevelEvent((self.wakeupPipe[0], "WAKE UP CLEARED"))
                os.read(self.wakeupPipe[0], 255)
                continue

            ch = self.chs[desc]

            if event & select.POLLERR == select.POLLERR:
                self._manageErroneousConnection(ch)
                continue

            if event & select.POLLOUT == select.POLLOUT:
                if ch.connecting:
                    self._completeConnectedSocket(ch)
                else:
                    self._writeSocket(ch)
            if event & select.POLLIN == select.POLLIN:
                if ch.listening:
                    self._createConnectedSocket(ch)
                else:
                    self._readSocket(ch)
            
            if event & select.POLLHUP == select.POLLHUP and event & select.POLLERR != select.POLLERR and event & select.POLLIN != select.POLLIN:
                ## Read/Write POLLHUP The other end has shut down one direction. (man:socket(7))
                ## or FD like pipe has been closed on the other end
                self.disconnect(ch.sid())

    def loop(self):
        """
            Do one loop. You should set a timemout to avoid being blocked in this call
            return True if it want to loop another time
            return False when it has nothing more to do.
        """
        self._managePollList()
        if self.connectionCount == 0 and not self.running:
            return False
        try:
            fdescs = self.poll.poll(self.timeouts.getNextTimeout())
            for e in self.timeouts.popPastEvents():
                self._throwLowLevelEvent((None, "TIMEOUT", e["handle"]))
                self._throwHighLevelEvent(("timeout", e["payload"]))
            if len(fdescs):
                for fdescState in fdescs:
                    self._throwLowLevelEvent((fdescState[0], convertPollState(fdescState[1])))
            else:
                self._throwLowLevelEvent((None, "LOOP"))
            self._managePollReturn(fdescs)
        except bdb.BdbQuit:
            raise
        except select.error, error:
            if error[0] != errno.EINTR:
                sys.excepthook(*sys.exc_info())
                self._throwLowLevelEvent((None, "EXCEPTION", sys.exc_info()))

        except:
            if sys.exc_info()[0] == KeyboardInterrupt:
                if self.stopOnKeyboardInterruptFlag:
                    self.stop()
                else:
                    self._throwHighLevelEvent(("keyboard interrupt",))
                    self._throwLowLevelEvent((None, "EXCEPTION", sys.exc_info()))
            else:
                sys.excepthook(*sys.exc_info())
                self._throwLowLevelEvent((None, "EXCEPTION", sys.exc_info()))
        return True

    def main(self):
        """
            Call me if you want that I manage the main execution loop. In this
            case, low lelvel events will be thrown at the start and at the stop.
        """
        self._throwLowLevelEvent((None, "MAIN LOOP STARTED"))
        while self.loop():
            pass 
        self._throwLowLevelEvent((None, "MAIN LOOP STOPPED"))

    def stop(self):
        """
            Stop the connection manager, and close each socket if any.
        """
        if self.connectionCount == 0 and not self.running:
            return
        self.running = False
        self.semaChs.acquire()
        for cid in self.chs.keys():
            try:
                self.disconnect(cid)
            except (ValueError, socket.error):
                ## When we stop a socket, another one can be closed at the same
                ## time returning us a ValueError
                pass
        self._wakeup("Alerts poll that manager is shutting down " + str(self.connectionCount) + " " + str([str(cid) + " " + convertPollState(ch.pollFor) for cid, ch in self.chs.items()]))
        self.semaChs.release()

    def stopAtLastSocketClosed(self, value = True):
        """
            Ask the communication to auto-stop if it doesn't manage connection
            anymore.
        """
        self.running = not value

    def stopOnException(self, value=True):
        """
            When an exception raise during a high level event dispatch, stop the manager.
        """
        self.stopOnExceptionFlag = value

    def stopOnKeyboardInterrupt(self, value = True):
        """
            Stop on ctrl + c
        """
        self.stopOnKeyboardInterruptFlag = value

    def listen(self, port=8417, ipV6=True, protoIn=None, protoOut=None, ssl=False):
        """
            Create a listening socket.

            @param protoIn: specific protocol callback (see CommunicationManager.__init__ doc)
            @param protoOut: specific protocol callback (see CommunicationManager.__init__ doc)
            @return: the id of the listening socket (only used to close it)
            @param ssl: Enable SSL
        """
        if ipV6:
            listening_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        else:
            listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ch = ConnectionHandle(self, listening_socket, protoIn, protoOut, ssl)
        ch.socket.bind(("", port))
        return self._addListeningSocket(ch, port)

    def listenUnix(self, address, protoIn=None, protoOut=None):
        """
            Create a listening socket, via unix socket.

            @param protoIn: specific protocol callback (see CommunicationManager.__init__ doc)
            @param protoOut: specific protocol callback (see CommunicationManager.__init__ doc)
            @return: the id of the listening socket (only used to close it)
        """
        listening_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        ch = ConnectionHandle(self, listening_socket, protoIn, protoOut, False)
        ch.socket.bind(address)
        return self._addListeningSocket(ch, address)

        
    def _addListeningSocket(self, ch, portOrAddress):
        # Socket can be reuse immediatly after closing
        ch.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        ch.socket.listen(5)
        self.semaChs.acquire()
        self.chs[ch.sid()] = ch
        self._throwLowLevelEvent((ch.sid(), "LISTENING", portOrAddress))
        self._throwHighLevelEvent(("listening", ch.sid()))
        ch.pollFor = select.POLLIN
        ch.listening = True
        self.connectionCount += 1
        self._wakeup("Registering new listening socket %d" % ch.sid())
        self.semaChs.release()
        return ch.sid()

    def _cidToCh(self, cid):
        try:
            return self.chs[cid]
        except KeyError:
            raise ValueError("CID not in use: %d" % cid)

    def disconnect(self, cid):
        """
            Disconnect a socket. Even when the connection is hold.
            
            @note: If ch.dontClose is set, just unmanage it.
        """
        ch = self._cidToCh(cid)
        ch.hold = False
        ch.pollFor &= ~select.POLLIN
        self._throwLowLevelEvent((ch.sid(), "DISCONNECTING"))
        self._wakeup("Alerts poll that socket %d is no more active" % ch.sid())

    close = disconnect

    def hold(self, cid, after=None):
        """
            Avoid pooling and reading from this socket. The in buffer is then
            no more filled.
            
            In this case, if data are coming from the network (or the other part
            of the pipe /whathever fd), it will stay in the kernel buffer, or
            will block on the other side, until you unhold this connection.
            
            @param after: Read "after" bytes before holding
        """
        ch = self._cidToCh(cid)
        if after is not None:
            ch.readUntil = after
            return
        ch.hold = True
        ch.pollFor &= ~select.POLLIN
        self._throwLowLevelEvent((ch.sid(), "HOLD"))
        self._wakeup("Alerts poll that socket %d is now being hold" % ch.sid())

    def unhold(self, cid):
        """
            Resume hold state.
            
            All data that are arrived from the network will be read.
        """
        ch = self._cidToCh(cid)
        ch.hold = False
        ch.pollFor |= select.POLLIN
        self._throwLowLevelEvent((ch.sid(), "UNHOLD"))
        self._wakeup("Alerts poll that socket %d is no more being hold" % ch.sid())

    def _translateAddress(self, address, port, ipV6):
        """
            Return the right network address given the address, port and familyt address
        """
        result = socket.getaddrinfo(address, port, socket.AF_INET6 if ipV6 else socket.AF_INET, socket.SOCK_STREAM)
        return result[0][4]

    def connect(self, address="ip6-localhost", port=8417, ipV6=True, protoIn=None, protoOut=None, ssl=False):
        """
            Connect to a peer.
            
            @param protoIn: specific protocol callback (see CommunicationManager.__init__ doc)
            @param protoOut: specific protocol callback (see CommunicationManager.__init__ doc)
            @return: the socket number, which is used as id or None if the
            connection fails at this step (a low level event is sent).
        """

        if ipV6:
            local_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        else:
            local_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ch = ConnectionHandle(self, local_socket, protoIn, protoOut, ssl)
        ch.socket.setblocking(False)
        try:
            self._throwLowLevelEvent((None, "WILL CONNECT TO", address, port, "IPV6 == " + str(ipV6)))
            translatedAddress = self._translateAddress(address, port, ipV6)
            ch.socket.connect(translatedAddress)
        except socket.error, error:
            if error[0] != errno.EINPROGRESS :
                self._throwLowLevelEvent((None, "EXCEPTION", sys.exc_info()))
                return None
        else:
            print >>sys.stderr, "Error : EINPROGRESS not returned."
        return self._addSocket(ch, translatedAddress)

    def connectUnix(self, address="/tmp", protoIn=None, protoOut=None):
        """
            Connect to a peer, via an unix socket.
            
            @param protoIn: specific protocol callback (see CommunicationManager.__init__ doc)
            @param protoOut: specific protocol callback (see CommunicationManager.__init__ doc)
            @return: the socket number, which is used as id or None if the
            connection fails at this step (a low level event is sent).
        """

        local_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        ch = ConnectionHandle(self, local_socket, protoIn, protoOut, False)
        ch.socket.setblocking(False)
        try:
            self._throwLowLevelEvent((None, "WILL CONNECT TO", address))
            ch.socket.connect(address)
        except socket.error, error:
            if error[0] != errno.EINPROGRESS :
                self._throwLowLevelEvent((None, "EXCEPTION", sys.exc_info()))
                return None
        return self._addSocket(ch, address)
        

    def _addSocket(self, ch, address):
        self.semaChs.acquire()
        self.chs[ch.sid()] = ch
        self._throwLowLevelEvent((ch.sid(), "CONNECTING", address, ch.socket.getsockname()))
        ch.connecting = True
        ch.pollFor |= select.POLLOUT
        self.connectionCount += 1
        self._wakeup("Alerts poll that a new socket %d is waiting for connection completition" % ch.sid())
        self.semaChs.release()
        return ch.sid()

    def _throwLowLevelEvent(self, event):
        for listener in self.lowLevelListeners:
            try:
                listener(event)
            except bdb.BdbQuit:
                raise
            except Exception:
                sys.excepthook(*sys.exc_info())

    def _throwHighLevelEvent(self, event):
        for listener in self.highLevelListeners:
            try:
                listener(event)
            except bdb.BdbQuit:
                raise
            except Exception:
                sys.excepthook(*sys.exc_info())
                if self.stopOnExceptionFlag:
                    self.stop()


    def registerLowLevelListener(self, listener):
        """ All things that refers to socket connection
        """
        self.lowLevelListeners += [listener]

    def registerHighLevelListener(self, listener):
        """ All things that refers to application
        """
        self.highLevelListeners += [listener]

    def unregisterLowLevelListener(self, listener):
        """
            Remove listener.
        """
        self.lowLevelListeners.remove(listener)

    def unregisterHighLevelListener(self, listener):
        """
            Remove listener.
        """
        self.highLevelListeners.remove(listener)


    def addFDescriptor(self, fd, protoIn=None, protoOut=None, dontClose=True, hold=False):
        """
            Add a file descriptor in the system.
            The connection manager has been designed to play with socket, so
            events labels will be a bit strange for simple FDs but the 
            meaning will be the same...
            
            @param fd: the file descriptor to listen to. Be sure not to call
            read or write operations on fds who are not able to do that. (write
            a read only file, for example)
            @param protoIn: specific protocol callback (see CommunicationManager.__init__ doc)
            @param protoOut: specific protocol callback (see CommunicationManager.__init__ doc)
            @param dontClose: disconnect option should't really close the FD. If
            the close operation of this FD is managed by another mean, set this
            to True. Default: True
            @param hold: this FD is added hold: no data will be read from it.
            
            @return: the fd, used as a cid
        """
        if fd in self.chs.keys():
            raise ValueError("FD already managed: %i" % fd)
        ch = ConnectionHandle(self, fd, protoIn, protoOut)
        ch.dontClose = dontClose
        self.semaChs.acquire()
        self.chs[ch.sid()] = ch
        self._throwLowLevelEvent((ch.sid(), "FD ADDED"))
        self._throwHighLevelEvent(("file descriptor managed", ch.sid()))
        self.connectionCount += 1
        self._wakeup("Alerts poll that a new FD %d has been added" % ch.sid())
        if hold:
            self.hold(fd)
        self.semaChs.release()
        return ch.sid()

    def removeFDescriptor(self, fd):
        """
            Remove a fd. 
            
            @param fd: the file descriptor
            @return: the file descriptor, as seen by the system (IE, the real
            socket object).
        """
        ch = self._cidToCh(fd)
        ch.dontClose = True
        self.disconnect(fd)
        return ch.socket
    
    def setTimeout(self, timeout, payload=None):
        """
            Throw a Timeout event when timeout ms has passed.
            @param timeout: timeout in seconds (as a float)
            @return: a timeout handle (as a int)
        """
        r = self.timeouts.addTimeout(timeout, payload)
        self._throwLowLevelEvent((None, "TIMEOUT ADDED", r, timeout))
        self._wakeup("New timout is set (%f s) %d" % (timeout, r))
        return r

    def cancelTimeout(self, handle):
        """
            Cancel a timeout
            @param handle: the previously given handle
        """
        self.timeouts.cancelTimeout(handle)
        self._throwLowLevelEvent((None, "TIMEOUT CANCELED", handle))

class TimeoutsManagement(object):
    def __init__(self):
        self.pendings = []
        self.nextHandle = 0
    
    def addTimeout(self, timeout, payload):
        """
            Add a new timeout in the list.
            @param timeout: time to wait, in seconds, as a float
            @param payload: some data which will be given back when event will
            arise.
            @return: a handle to manage the new event
        """
        tt = time.time() + timeout
        event = {
            "time": tt,
            "payload": payload,
            "handle": self.nextHandle,
        }
        self.nextHandle += 1
        pos = 0

        while pos < len(self.pendings) and self.pendings[pos]["time"] < tt:
            pos += 1
        self.pendings.insert(pos, event)
        return event["handle"]

    def cancelTimeout(self, handle):
        """
            Remove the handle from the list
        """
        for e in self.pendings:
            if e["handle"] == handle:
                self.pendings.remove(e)
                return
            

    def getNextTimeout(self):
        """
            Return the next timeout to wait for or None if there is no reason to
            timeout.
            @return: timeout, in milliseconds
        """
        if len(self.pendings) == 0:
            return None
        now = time.time()
        return (self.pendings[0]["time"] - now) * 1000
    
    def popPastEvents(self):
        """
            Return, and remove, the events that have to be treated.
        """
        result = []
        now = time.time()
        for e in self.pendings:
            if e["time"] < now:
                result.append(e)
        self.pendings = self.pendings[len(result):]
        return result
        

pollStates = ["POLLIN", "POLLPRI", "POLLOUT", "POLLERR", "POLLHUP", "POLLNVAL"]
pollMap = {} #: @undocumented
for state in pollStates :
    pollMap[eval("select." + state)] = state

# some cleanup is always welcome.
del state 
del pollStates

def convertPollState(state):
    """
        Given a value of ORed select states (POLLIN | POLLERR...), return a
        string with the names of the states marged with spaces ("POLLIN POLLERR").
    """
   
    readableState = ""
    mark = 1
    for i in range(8):
        if mark & state:
           readableState += pollMap[mark & state] + " "
        mark <<= 1
    return readableState.strip()

def returnRaw(ch):
    """
        Default protoIn callback. Return all data as string.
    """
    data = ch.getInData()
    ch.clearInData()
    return (ch.OK, [data])

def returnIdentity(data):
    """
        Default protoOut callback. Return all data as string.
    """
    return "".join([str(d) for d in data])


def allLevelListener(event):
    """
        Basic debug callback to see what's happen'.
    """
    pprint.pprint(event)
    #sys.excepthook(*event[2])

## Running the module should'n raise any exception. It should test most features
## but is not considered a real test case since received events are not
## checked.
if __name__ == "__main__" :
    com = CommunicationManager(blocking=False)
    com.registerLowLevelListener(allLevelListener)
    com.registerHighLevelListener(allLevelListener)
    try :
        b = com.listen()
        assert com.connect() == 6
        
        (pin, pout) = os.pipe()
        com.addFDescriptor(pout)
        com.sendRaw(pout, "plop 1")
        print "----->", os.read(pin, 255)
        com.removeFDescriptor(pout)
        com.addFDescriptor(pin)
        os.write(pout, "plop 2")

        com.sendRaw(6, "plop 3")
        com.send(7, "plop 4")
        com.addFDescriptor(0)
        com.addFDescriptor(1)
        com.removeFDescriptor(1)
        os.close(pout)
        time.sleep(1)
        a = com.removeFDescriptor(7)
        com.removeFDescriptor(0)
        com.close(b)
        time.sleep(1)
        
        assert com.listenUnix("/tmp/testComManager") == 5
        time.sleep(1)
        assert com.connectUnix("/tmp/testComManager") == 9
        time.sleep(1)
        com.sendRaw(9, "plopretour")
        com.sendRaw(10, "plop")
        time.sleep(1)
        com.close(5)
        com.close(10)
        
    except:
        sys.excepthook(*sys.exc_info())
    com.stop()

