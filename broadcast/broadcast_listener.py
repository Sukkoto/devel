

"""
.. module:: broadcast_listener
.. role:: red

BitDust broadcast_listener() Automat

EVENTS:
    * :red:`broadcaster-connected`
    * :red:`connect`
    * :red:`disconnect`
    * :red:`incoming-message`
    * :red:`init`
    * :red:`lookup-failed`
    * :red:`message-failed`
    * :red:`outbound-message`
    * :red:`shutdown`
"""

#------------------------------------------------------------------------------ 

_Debug = False
_DebugLevel = 6

#------------------------------------------------------------------------------ 

from automats import automat

from userid import my_id

from transport import callback

from p2p import p2p_service
from p2p import commands

#------------------------------------------------------------------------------ 

_BroadcastListener = None

#------------------------------------------------------------------------------ 

def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _BroadcastListener
    if event is None and arg is None:
        return _BroadcastListener
    if _BroadcastListener is None:
        # set automat name and starting state here
        _BroadcastListener = BroadcastListener('broadcast_listener', 'AT_STARTUP', _DebugLevel, _Debug)
    if event is not None:
        _BroadcastListener.automat(event, arg)
    return _BroadcastListener

#------------------------------------------------------------------------------ 

class BroadcastListener(automat.Automat):
    """
    This class implements all the functionality of the ``broadcast_listener()`` state machine.
    """

    def init(self):
        """
        Method to initialize additional variables and flags
        at creation phase of broadcast_listener() machine.
        """
        self.broadcaster_idurl = None
        self.incoming_broadcast_message_callback = None

    def A(self, event, arg):
        """
        The state machine code, generated using `visio2python <http://bitdust.io/visio2python/>`_ tool.
        """
        if self.state == 'AT_STARTUP':
            if event == 'init':
                self.state = 'OFFLINE'
                self.doInit(arg)
        elif self.state == 'BROADCASTER?':
            if event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
            elif event == 'disconnect' or event == 'lookup-failed':
                self.state = 'OFFLINE'
            elif event == 'broadcaster-connected':
                self.state = 'LISTENING'
                self.doSetBroadcaster(arg)
        elif self.state == 'LISTENING':
            if event == 'disconnect' or event == 'message-failed':
                self.state = 'OFFLINE'
                self.doRemoveBroadcaster(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doRemoveBroadcaster(arg)
                self.doDestroyMe(arg)
            elif event == 'outbound-message':
                self.doSendMessageToBroadcaster(arg)
            elif event == 'incoming-message':
                self.doNotifyInputMessage(arg)
        elif self.state == 'OFFLINE':
            if event == 'connect':
                self.state = 'BROADCASTER?'
                self.doStartBroadcasterLookup(arg)
            elif event == 'shutdown':
                self.state = 'CLOSED'
                self.doDestroyMe(arg)
        elif self.state == 'CLOSED':
            pass
        return None

    def doInit(self, arg):
        """
        Action method.
        """
        self.incoming_broadcast_message_callback = arg
        callback.append_inbox_callback(self._on_inbox_packet)

    def doStartBroadcasterLookup(self, arg):
        """
        Action method.
        """
        from broadcast import broadcasters_finder
        broadcasters_finder.A('start',
            (self.automat, 'listen ' + my_id.getLocalID(), []))

    def doSetBroadcaster(self, arg):
        """
        Action method.
        """
        self.broadcaster_idurl = arg

    def doRemoveBroadcaster(self, arg):
        """
        Action method.
        """
        self.broadcaster_idurl = None

    def doSendMessageToBroadcaster(self, arg):
        """
        Action method.
        """
        p2p_service.SendBroadcastMessage(self.broadcaster_idurl, arg)

    def doNotifyInputMessage(self, arg):
        """
        Action method.
        """
        if self.incoming_broadcast_message_callback is not None:
            self.incoming_broadcast_message_callback(arg)

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        self.incoming_broadcast_message_callback = None
        callback.remove_inbox_callback(self._on_inbox_packet)
        automat.objects().pop(self.index)
        global _BroadcastListener
        del _BroadcastListener
        _BroadcastListener = None

    #-----------------------------------------------------------------------------

    def _on_inbox_packet(self, newpacket, info, status, error_message):
        if status != 'finished':
            return False
        if newpacket.Command == commands.Broadcast():
            from broadcast import broadcast_service
            msg = broadcast_service.read_message_from_packet(newpacket)
            if not msg:
                return False
            if newpacket.CreatorID == self.broadcaster_idurl:
                self.automat('incoming-message', (msg, newpacket))
                return True
        return False
        
        
        
        
        