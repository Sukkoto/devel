

"""
.. module:: supplier_finder
.. role:: red
BitPie.NET supplier_finder() Automat


EVENTS:
    * :red:`found-one-user`
    * :red:`inbox-packet`
    * :red:`start`
    * :red:`supplier-connected`
    * :red:`supplier-not-connected`
    * :red:`timer-10sec`
    * :red:`users-not-found`

"""

import time
import random

import lib.dhnio as dhnio
import lib.automat as automat
import lib.commands as commands
import lib.contacts as contacts
import lib.eccmap as eccmap
import lib.misc as misc
import lib.settings as settings
import lib.diskspace as diskspace

import userid.identitycache as identitycache
import transport.callback as callback
import dht.dht_service as dht_service

import fire_hire
import p2p_service
import backup_control
import supplier_connector 

#------------------------------------------------------------------------------ 

_SupplierFinder = None

#------------------------------------------------------------------------------ 

def A(event=None, arg=None):
    """
    Access method to interact with the state machine.
    """
    global _SupplierFinder
    if _SupplierFinder is None:
        # set automat name and starting state here
        _SupplierFinder = SupplierFinder('supplier_finder', 'AT_STARTUP', 6)
    if event is not None:
        _SupplierFinder.automat(event, arg)
    return _SupplierFinder


class SupplierFinder(automat.Automat):
    """
    This class implements all the functionality of the ``supplier_finder()`` state machine.
    """

    timers = {
        'timer-10sec': (10.0, ['ACK?','SERVICE?']),
        }

    def init(self):
        """
        Method to initialize additional variables and flags at creation of the state machine.
        """
        self.target_idurl = None

    def state_changed(self, oldstate, newstate):
        """
        Method to to catch the moment when automat's state were changed.
        """
        # fire_hire.A('supplier_finder.state', newstate)

    def A(self, event, arg):
        #---AT_STARTUP---
        if self.state == 'AT_STARTUP':
            if event == 'start' :
                self.state = 'RANDOM_USER'
                self.Attempts=0
                self.doInit(arg)
                self.doDHTFindRandomUser(arg)
        #---ACK?---
        elif self.state == 'ACK?':
            if event == 'timer-10sec' and self.Attempts<10 :
                self.state = 'RANDOM_USER'
                self.doDHTFindRandomUser(arg)
            elif self.Attempts>=10 and event == 'timer-10sec' :
                self.state = 'FAILED'
                fire_hire.A('search-failed')
                self.doDestroyMe(arg)
            elif event == 'inbox-packet' and self.isAckFromUser(arg) :
                self.state = 'SERVICE?'
                self.doSupplierConnect(arg)
        #---FAILED---
        elif self.state == 'FAILED':
            pass
        #---DONE---
        elif self.state == 'DONE':
            pass
        #---RANDOM_USER---
        elif self.state == 'RANDOM_USER':
            if event == 'users-not-found' :
                self.state = 'FAILED'
                fire_hire.A('search-failed')
                self.doDestroyMe(arg)
            elif event == 'found-one-user' :
                self.state = 'ACK?'
                self.doRememberUser(arg)
                self.Attempts+=1
                self.doSendMyIdentity(arg)
        #---SERVICE?---
        elif self.state == 'SERVICE?':
            if event == 'timer-10sec' and self.Attempts<10 :
                self.state = 'RANDOM_USER'
                self.doDHTFindRandomUser(arg)
            elif self.Attempts>=10 and event == 'timer-10sec' :
                self.state = 'FAILED'
                fire_hire.A('search-failed')
                self.doDestroyMe(arg)
            elif self.Attempts<10 and event == 'supplier-not-connected' :
                self.state = 'RANDOM_USER'
                self.doDHTFindRandomUser(arg)
            elif event == 'supplier-connected' :
                self.state = 'DONE'
                fire_hire.A('supplier-connected', self.target_idurl)
                self.doDestroyMe(arg)

    def isAckFromUser(self, arg):
        """
        Condition method.
        """
        newpacket, info, status, error_message = arg
        if newpacket.Command == commands.Ack():
            if newpacket.OwnerID == self.target_idurl:
                return True
        return False

#    def isServiceAccepted(self, arg):
#        """
#        Condition method.
#        """
#        newpacket, info, status, error_message = arg
#        if newpacket.Command == commands.Ack():
#            if newpacket.Payload.startswith('accepted'):
#                return True
#        return False

    def doInit(self, arg):
        """
        Action method.
        """
        callback.add_inbox_callback(self._inbox_packet_received)

    def doSendMyIdentity(self, arg):
        """
        Action method.
        """
        p2p_service.SendIdentity(self.target_idurl, wide=True)

    def doSupplierConnect(self, arg):
        """
        Action method.
        """
        sc = supplier_connector.by_idurl(self.target_idurl)
        if not sc:
            sc = supplier_connector.create(self.target_idurl)
        sc.automat('connect')
        sc.set_callback('supplier_finder', self._supplier_connector_state)
            
    def doDHTFindRandomUser(self, arg):
        """
        Action method.
        """
        def _find(x):
            d = dht_service.find_node(dht_service.random_key())
            d.addCallback(self._found_nodes)
            d.addErrback(self._search_nodes_failed)
        d = dht_service.reconnect()
        d.addCallback(_find)        

    def doRememberUser(self, arg):
        """
        Action method.
        """
        self.target_idurl = arg

    def doDestroyMe(self, arg):
        """
        Remove all references to the state machine object to destroy it.
        """
        callback.remove_inbox_callback(self._inbox_packet_received)
        if self.target_idurl:
            sc = supplier_connector.by_idurl(self.target_idurl)
            if sc:
                sc.remove_callback('supplier_finder')
            self.target_idurl = None
        automat.objects().pop(self.index)
        global _SupplierFinder
        del _SupplierFinder
        _SupplierFinder = None

    def _inbox_packet_received(self, newpacket, info, status, error_message):
        """
        """
        self.automat('inbox-packet', (newpacket, info, status, error_message))
        
    def _found_nodes(self, nodes):
        dhnio.Dprint(18, 'supplier_finder._found_nodes %d nodes' % len(nodes))
        if len(nodes) > 0:
            node = random.choice(nodes)
            d = node.request('idurl')
            d.addBoth(self._got_target_idurl)
        else:
            self.automat('users-not-found')
    
    def _search_nodes_failed(self, err):
        self.automat('users-not-found')
    
    def _got_target_idurl(self, response):
        dhnio.Dprint(18, 'supplier_finder._got_target_idurl response=%s' % str(response) )
        try:
            idurl = response['idurl']
        except:
            idurl = None
        if not idurl or idurl == 'None':
            self.automat('users-not-found')
            return response
        if contacts.IsSupplier(idurl):
            dhnio.Dprint(18, '    %s is supplier already' % idurl)
            self.automat('users-not-found')
            return response
        d = identitycache.immediatelyCaching(idurl)
        d.addCallback(lambda x: self.automat('found-one-user', idurl))
        d.addErrback(lambda x: self.automat('users-not-found'))
        return response
            
    def _got_target_identity(self, pagesrc, idurl):
        self.automat('found-one-user', idurl)
        
    def _supplier_connector_state(self, supplier_idurl, newstate):
        if supplier_idurl != self.target_idurl:
            return
        # sc = supplier_connector.by_idurl(self.target_idurl)
        # if sc:
        #     sc.remove_callback('supplier_finder')
        if newstate is 'CONNECTED':
            self.automat('supplier-connected', self.target_idurl)
        elif newstate in ['DISCONNECTED', 'NO_SERVICE', ]:
            self.automat('supplier-not-connected')
        else:
            pass

