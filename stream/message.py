#!/usr/bin/python
# message.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (message.py) is part of BitDust Software.
#
# BitDust is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BitDust Software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with BitDust Software.  If not, see <http://www.gnu.org/licenses/>.
#
# Please contact us if you have any questions at bitdust.io@gmail.com
#
#
#
#

"""
.. module:: message

"""

#------------------------------------------------------------------------------

from __future__ import absolute_import

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

import time
import base64

#------------------------------------------------------------------------------

from twisted.internet.defer import fail
from twisted.internet.defer import Deferred

#------------------------------------------------------------------------------

from logs import lg

from p2p import commands
from p2p import online_status
from p2p import p2p_service

from lib import packetid
from lib import utime
from lib import serialization
from lib import strng

from crypt import key
from crypt import my_keys

from contacts import identitycache

from userid import id_url
from userid import my_id
from userid import global_id

#------------------------------------------------------------------------------

MAX_PENDING_MESSAGES_PER_CONSUMER = 100

#------------------------------------------------------------------------------

_ConsumersCallbacks = {}
_ReceivedMessagesIDs = []

_IncomingMessageCallbacks = []
_OutgoingMessageCallbacks = []

_MessageQueuePerConsumer = {}

_LastUserPingTime = {}
_PingTrustIntervalSeconds = 60 * 5

#------------------------------------------------------------------------------


def init():
    if _Debug:
        lg.out(_DebugLevel, "message.init")
    AddIncomingMessageCallback(push_incoming_message)
    AddOutgoingMessageCallback(push_outgoing_message)


def shutdown():
    if _Debug:
        lg.out(_DebugLevel, "message.shutdown")
    RemoveOutgoingMessageCallback(push_outgoing_message)
    RemoveIncomingMessageCallback(push_incoming_message)

#------------------------------------------------------------------------------

def received_messages_ids(erase_old_records=False):
    global _ReceivedMessagesIDs
    if erase_old_records:
        _ReceivedMessagesIDs = _ReceivedMessagesIDs[50:]
    return _ReceivedMessagesIDs


def message_queue():
    global _MessageQueuePerConsumer
    return _MessageQueuePerConsumer


def consumers_callbacks():
    global _ConsumersCallbacks
    return _ConsumersCallbacks

#------------------------------------------------------------------------------

def ConnectCorrespondent(idurl):
    pass


def UniqueID():
    return str(int(time.time() * 100.0))

#------------------------------------------------------------------------------

def AddIncomingMessageCallback(cb):
    """
    Calling with: (packet_in_object, private_message_object, decrypted_message_body)
    """
    global _IncomingMessageCallbacks
    if cb not in _IncomingMessageCallbacks:
        _IncomingMessageCallbacks.append(cb)
    else:
        lg.warn('callback method already exist')


def InsertIncomingMessageCallback(cb):
    """
    Calling with: (packet_in_object, private_message_object, decrypted_message_body)
    """
    global _IncomingMessageCallbacks
    if cb not in _IncomingMessageCallbacks:
        _IncomingMessageCallbacks.insert(0, cb)
    else:
        lg.warn('callback method already exist')


def RemoveIncomingMessageCallback(cb):
    """
    """
    global _IncomingMessageCallbacks
    if cb in _IncomingMessageCallbacks:
        _IncomingMessageCallbacks.remove(cb)
    else:
        lg.warn('callback method not exist')


def AddOutgoingMessageCallback(cb):
    """
    Calling with: (message_body, private_message_object, remote_identity, outpacket, packet_out_object)
    """
    global _OutgoingMessageCallbacks
    if cb not in _OutgoingMessageCallbacks:
        _OutgoingMessageCallbacks.append(cb)
    else:
        lg.warn('callback method already exist')


def RemoveOutgoingMessageCallback(cb):
    """
    """
    global _OutgoingMessageCallbacks
    if cb in _OutgoingMessageCallbacks:
        _OutgoingMessageCallbacks.remove(cb)
    else:
        lg.warn('callback method not exist')

#------------------------------------------------------------------------------

class PrivateMessage(object):
    """
    A class to represent a message.

    We always encrypt messages with a session key so we need to package
    with encrypted body.
    """

    def __init__(self, recipient_global_id, sender=None, encrypted_session=None, encrypted_body=None):
        self.sender = strng.to_text(sender or my_id.getGlobalID(key_alias='master'))
        self.recipient = strng.to_text(recipient_global_id)
        self.encrypted_session = encrypted_session
        self.encrypted_body = encrypted_body
        if _Debug:
            lg.out(_DebugLevel, 'message.%s created' % self)

    def __str__(self):
        return 'PrivateMessage (%r->%r) : %r %r' % (
            self.sender,
            self.recipient,
            type(self.encrypted_session),
            type(self.encrypted_body),
        )

    def sender_id(self):
        return self.sender

    def recipient_id(self):
        return self.recipient

    def session_key(self):
        return self.encrypted_session

    def body(self):
        return self.encrypted_body

    def encrypt(self, message_body, encrypt_session_func=None):
        new_sessionkey = key.NewSessionKey(session_key_type=key.SessionKeyType())
        if not encrypt_session_func:
            if my_keys.is_key_registered(self.recipient):
                if _Debug:
                    lg.out(_DebugLevel, 'message.PrivateMessage.encrypt with "%s" key' % self.recipient)
                encrypt_session_func = lambda inp: my_keys.encrypt(self.recipient, inp)
        if not encrypt_session_func:
            glob_id = global_id.ParseGlobalID(self.recipient)
            if glob_id['key_alias'] == 'master':
                if glob_id['idurl'] == my_id.getLocalID():
                    lg.warn('making private message addressed to me ???')
                    if _Debug:
                        lg.out(_DebugLevel, 'message.PrivateMessage.encrypt with "master" key')
                    encrypt_session_func = lambda inp: my_keys.encrypt('master', inp)
                else:
                    remote_identity = identitycache.FromCache(glob_id['idurl'])
                    if not remote_identity:
                        raise Exception('remote identity is not cached yet, not able to encrypt the message')
                    if _Debug:
                        lg.out(_DebugLevel, 'message.PrivateMessage.encrypt with remote identity public key')
                    encrypt_session_func = remote_identity.encrypt
            else:
                own_key = global_id.MakeGlobalID(idurl=my_id.getLocalID(), key_alias=glob_id['key_alias'])
                if my_keys.is_key_registered(own_key):
                    if _Debug:
                        lg.out(_DebugLevel, 'message.PrivateMessage.encrypt with "%s" key' % own_key)
                    encrypt_session_func = lambda inp: my_keys.encrypt(own_key, inp)
        if not encrypt_session_func:
            raise Exception('can not find key for given recipient')
        self.encrypted_session = encrypt_session_func(new_sessionkey)
        self.encrypted_body = key.EncryptWithSessionKey(new_sessionkey, message_body, session_key_type=key.SessionKeyType())
        return self.encrypted_session, self.encrypted_body

    def decrypt(self, decrypt_session_func=None):
        if not decrypt_session_func:
            if my_keys.is_key_registered(self.recipient):
                if _Debug:
                    lg.out(_DebugLevel, 'message.PrivateMessage.decrypt with "%s" key' % self.recipient)
                decrypt_session_func = lambda inp: my_keys.decrypt(self.recipient, inp)
        if not decrypt_session_func:
            glob_id = global_id.ParseGlobalID(self.recipient)
            if glob_id['idurl'] == my_id.getLocalID():
                if glob_id['key_alias'] == 'master':
                    if _Debug:
                        lg.out(_DebugLevel, 'message.PrivateMessage.decrypt with "master" key')
                    decrypt_session_func = lambda inp: my_keys.decrypt('master', inp)
        if not decrypt_session_func:
            raise Exception('can not find key for given recipient: %s' % self.recipient)
        decrypted_sessionkey = decrypt_session_func(self.encrypted_session)
        return key.DecryptWithSessionKey(decrypted_sessionkey, self.encrypted_body, session_key_type=key.SessionKeyType())

    def serialize(self):
        dct = {
            'r': self.recipient,
            's': self.sender,
            'k': strng.to_text(base64.b64encode(strng.to_bin(self.encrypted_session))),
            'p': self.encrypted_body,
        }
        return serialization.DictToBytes(dct, encoding='utf-8')

    @staticmethod
    def deserialize(input_string):
        try:
            dct = serialization.BytesToDict(input_string, keys_to_text=True, encoding='utf-8')
            _recipient = strng.to_text(dct['r'])
            _sender = strng.to_text(dct['s'])
            _encrypted_session_key=base64.b64decode(strng.to_bin(dct['k']))
            _encrypted_body = dct['p']
            message_obj = PrivateMessage(
                recipient_global_id=_recipient,
                sender=_sender,
                encrypted_session=_encrypted_session_key,
                encrypted_body=_encrypted_body,
            )
        except:
            lg.exc()
            return None
        return message_obj


#------------------------------------------------------------------------------

def on_incoming_message(request, info, status, error_message):
    """
    Message came in for us
    """
    global _IncomingMessageCallbacks
    if _Debug:
        lg.out(_DebugLevel, "message.on_incoming_message new PrivateMessage %r from %s" % (request.PacketID, request.OwnerID, ))
    private_message_object = PrivateMessage.deserialize(request.Payload)
    if private_message_object is None:
        lg.err("PrivateMessage deserialize failed, can not extract message from request payload of %d bytes" % len(request.Payload))
        return False
    try:
        decrypted_message = private_message_object.decrypt()
        json_message = serialization.BytesToDict(
            decrypted_message,
            unpack_types=True,
            encoding='utf-8',
        )
    except:
        lg.exc()
        return False
    if request.PacketID in received_messages_ids():
        lg.warn("skip incoming message %s because found in recent history" % request.PacketID)
        return False
    received_messages_ids().append(request.PacketID)
    if len(received_messages_ids()) > 100:
        received_messages_ids(True)
    handled = False
    try:
        for cb in _IncomingMessageCallbacks:
            handled = cb(request, private_message_object, json_message)
            if _Debug:
                lg.args(_DebugLevel, cb=cb, packet_id=request.PacketID, handled=handled)
            if handled:
                break
    except:
        lg.exc()
    if _Debug:
        lg.args(_DebugLevel, msg=json_message, handled=handled)
    return True


def on_ping_success(ok, idurl):
    global _LastUserPingTime
    idurl = id_url.to_bin(idurl)
    _LastUserPingTime[idurl] = time.time()
    lg.info('shake up hands %r before sending a message : %s' % (idurl, ok, ))
    return ok


def on_message_delivered(idurl, json_data, recipient_global_id, packet_id, response, info, result_defer=None):
    global _LastUserPingTime
    idurl = id_url.to_bin(idurl)
    if _Debug:
        lg.args(_DebugLevel, idurl=idurl, packet_id=packet_id, recipient_global_id=recipient_global_id)
    _LastUserPingTime[idurl] = time.time()
    if result_defer and not result_defer.called:
        result_defer.callback(response)


def on_message_failed(idurl, json_data, recipient_global_id, packet_id, response, info, result_defer=None, error=None):
    global _LastUserPingTime
    idurl = id_url.to_bin(idurl)
    lg.err('message %s failed sending to %s in %s / %s because %r' % (
        packet_id, recipient_global_id, response, info, error, ))
    if idurl in _LastUserPingTime:
        _LastUserPingTime[idurl] = 0
    if result_defer and not result_defer.called:
        err = Exception(response) if response else (error if not strng.is_string(error) else Exception(error))
        result_defer.errback(err)

#------------------------------------------------------------------------------

def do_send_message(json_data, recipient_global_id, packet_id, message_ack_timeout, result_defer=None, fire_callbacks=True):
    global _OutgoingMessageCallbacks
    remote_idurl = global_id.GlobalUserToIDURL(recipient_global_id, as_field=False)
    if not remote_idurl:
        raise Exception('invalid recipient')
    remote_identity = identitycache.FromCache(remote_idurl)
    if not remote_identity:
        raise Exception('remote identity object not exist in cache')
    message_body = serialization.DictToBytes(
        json_data,
        pack_types=True,
        encoding='utf-8',
    )
    if _Debug:
        lg.out(_DebugLevel, "message.do_send_message to %s with %d bytes message timeout=%s" % (
            recipient_global_id, len(message_body), message_ack_timeout))
    try:
        private_message_object = PrivateMessage(recipient_global_id=recipient_global_id)
        private_message_object.encrypt(message_body)
    except:
        lg.exc()
        raise Exception('message encryption failed')
    payload = private_message_object.serialize()
    if _Debug:
        lg.out(_DebugLevel, "        payload is %d bytes, remote idurl is %s" % (len(payload), remote_idurl))
    result, outpacket = p2p_service.SendMessage(
        remote_idurl=remote_idurl,
        packet_id=packet_id,
        payload=payload,
        callbacks={
            commands.Ack(): lambda response, info: on_message_delivered(
                remote_idurl, json_data, recipient_global_id, packet_id, response, info, result_defer, ),
            commands.Fail(): lambda response, info: on_message_failed(
                remote_idurl, json_data, recipient_global_id, packet_id, response, info,
                result_defer=result_defer, error='fail received'),
            None: lambda pkt_out: on_message_failed(
                remote_idurl, json_data, recipient_global_id, packet_id, None, None,
                result_defer=result_defer, error='timeout', ),
        },
        response_timeout=message_ack_timeout,
    )
    if fire_callbacks:
        try:
            for cp in _OutgoingMessageCallbacks:
                cp(json_data, private_message_object, remote_identity, outpacket, result)
        except:
            lg.exc()
            raise Exception('failed sending message')
    return result


def send_message(json_data, recipient_global_id, packet_id=None,
                 message_ack_timeout=None, ping_timeout=20, ping_retries=0,
                 skip_handshake=False, fire_callbacks=True):
    """
    Send command.Message() packet to remote peer. Returns Deferred object.
    """
    global _LastUserPingTime
    global _PingTrustIntervalSeconds
    if not packet_id:
        packet_id = packetid.UniqueID()
    if _Debug:
        lg.out(_DebugLevel, "message.send_message to %s with PacketID=%s ping_timeout=%d message_ack_timeout=%r ping_retries=%d" % (
            recipient_global_id, packet_id, ping_timeout, message_ack_timeout, ping_retries, ))
    remote_idurl = global_id.GlobalUserToIDURL(recipient_global_id, as_field=False)
    if not remote_idurl:
        lg.warn('invalid recipient')
        return fail(Exception('invalid recipient'))
    ret = Deferred()
    if remote_idurl not in _LastUserPingTime:
        is_ping_expired = True
    else:
        is_ping_expired = time.time() - _LastUserPingTime[remote_idurl] > _PingTrustIntervalSeconds
    remote_identity = identitycache.FromCache(remote_idurl)
    is_online = online_status.isOnline(remote_idurl)
    if _Debug:
        lg.out(_DebugLevel, "    is_ping_expired=%r  remote_identity=%r  is_online=%r  skip_handshake=%r" % (
            is_ping_expired, bool(remote_identity), is_online, skip_handshake, ))
    if remote_identity is None or ((is_ping_expired or not is_online) and not skip_handshake):
        d = online_status.handshake(
            idurl=remote_idurl,
            ack_timeout=ping_timeout,
            ping_retries=ping_retries,
            channel='send_message',
            keep_alive=True,
        )
        d.addCallback(lambda ok: on_ping_success(ok, remote_idurl))
        d.addCallback(lambda _: do_send_message(
            json_data=json_data,
            recipient_global_id=recipient_global_id,
            packet_id=packet_id,
            message_ack_timeout=message_ack_timeout,
            result_defer=ret,
            fire_callbacks=fire_callbacks,
        ))
        d.addErrback(lambda err: on_message_failed(
            remote_idurl, json_data, recipient_global_id, packet_id, None, None, result_defer=ret, error=err))
        return ret
    try:
        do_send_message(
            json_data=json_data,
            recipient_global_id=recipient_global_id,
            packet_id=packet_id,
            message_ack_timeout=message_ack_timeout,
            result_defer=ret,
            fire_callbacks=fire_callbacks,
        )
    except Exception as exc:
        lg.warn(str(exc))
        on_message_failed(remote_idurl, json_data, recipient_global_id, packet_id, None, None, error=exc)
        ret.errback(exc)
    return ret

#------------------------------------------------------------------------------

def consume_messages(consumer_id, callback=None, direction=None, message_types=None, reset_callback=False):
    """
    """
    if consumer_id in consumers_callbacks():
        if not reset_callback:
            raise Exception('consumer callback already exist')
        clear_consumer_callbacks(consumer_id)
    cb = callback or Deferred()
    consumers_callbacks()[consumer_id] = {
        'callback': cb,
        'direction': direction,
        'message_types': message_types,
    }
    if _Debug:
        lg.out(_DebugLevel, 'message.consume_messages added callback for consumer %r' % consumer_id)
    # reactor.callLater(0, do_read)  # @UndefinedVariable
    do_read()
    return cb


def clear_consumer_callbacks(consumer_id):
    if consumer_id not in consumers_callbacks().keys():
        return True
    cb_info = consumers_callbacks().pop(consumer_id)
    if isinstance(cb_info['callback'], Deferred):
        if _Debug:
            lg.args(_DebugLevel, consumer_id=consumer_id, cb=cb_info['callback'], called=cb_info['callback'].called)
        if not cb_info['callback'].called:
            cb_info['callback'].callback([])
    else:
        if _Debug:
            lg.args(_DebugLevel, consumer_id=consumer_id, cb=cb_info['callback'], called='skipping callable method')
    return True

#------------------------------------------------------------------------------

def push_incoming_message(request, private_message_object, json_message):
    """
    """
    for consumer_id in consumers_callbacks().keys():
        if consumer_id not in message_queue():
            message_queue()[consumer_id] = []
        msg_type = 'private_message'
        if request.PacketID.startswith('queue_'):
            msg_type = 'queue_message'
        elif request.PacketID.startswith('qreplica_'):
            msg_type = 'queue_message_replica'
        message_queue()[consumer_id].append({
            'type': msg_type,
            'dir': 'incoming',
            'to': private_message_object.recipient_id(),
            'from': private_message_object.sender_id(),
            'data': json_message,
            'packet_id': request.PacketID,
            'owner_idurl': request.OwnerID,
            'time': utime.get_sec1970(),
        })
        if _Debug:
            lg.out(_DebugLevel, 'message.push_incoming_message "%s" for consumer "%s", %d pending messages for consumer %r' % (
                request.PacketID, consumer_id, len(message_queue()[consumer_id]), consumer_id, ))
    # reactor.callLater(0, do_read)  # @UndefinedVariable
    total_consumed = do_read()
    return total_consumed > 0


def push_outgoing_message(json_message, private_message_object, remote_identity, request, result):
    """
    """
    for consumer_id in consumers_callbacks().keys():
        if consumer_id not in message_queue():
            message_queue()[consumer_id] = []
        msg_type = 'private_message'
        if request.PacketID.startswith('queue_'):
            msg_type = 'queue_message'
        elif request.PacketID.startswith('qreplica_'):
            msg_type = 'queue_message_replica'
        message_queue()[consumer_id].append({
            'type': msg_type,
            'dir': 'outgoing',
            'to': private_message_object.recipient_id(),
            'from': private_message_object.sender_id(),
            'data': json_message,
            'packet_id': request.PacketID,
            'owner_idurl': request.OwnerID,
            'time': utime.get_sec1970(),
        })
        if _Debug:
            lg.out(_DebugLevel, 'message.push_outgoing_message "%s" for consumer "%s", %d pending messages for consumer %r' % (
                request.PacketID, consumer_id, len(message_queue()[consumer_id]), consumer_id, ))
    # reactor.callLater(0, do_read)  # @UndefinedVariable
    do_read()
    return False


def push_group_message(json_message, direction, group_key_id, producer_id, sequence_id):
    for consumer_id in consumers_callbacks().keys():
        if consumer_id not in message_queue():
            message_queue()[consumer_id] = []
        message_queue()[consumer_id].append({
            'type': 'group_message',
            'dir': direction,
            'to': group_key_id,
            'from': producer_id,
            'data': json_message,
            'packet_id': sequence_id,
            'owner_idurl': None,
            'time': utime.get_sec1970(),
        })
        if _Debug:
            lg.out(_DebugLevel, 'message.push_group_message "%d" at group "%s", %d pending messages for consumer %s' % (
                sequence_id, group_key_id, len(message_queue()[consumer_id]), consumer_id, ))
    # reactor.callLater(0, do_read)  # @UndefinedVariable
    do_read()
    return True

#------------------------------------------------------------------------------

def do_read():
    """
    """
    known_consumers = list(message_queue().keys())
    total_consumed = 0
    for consumer_id in known_consumers:
        if consumer_id not in message_queue() or len(message_queue()[consumer_id]) == 0:
            continue
        cb_info = consumers_callbacks().get(consumer_id)
        pending_messages = message_queue()[consumer_id]
        # no consumer or queue is growing too much -> stop consumer and queue
        if (not cb_info or not cb_info['callback']) or len(pending_messages) > MAX_PENDING_MESSAGES_PER_CONSUMER:
            consumers_callbacks().pop(consumer_id, None)
            message_queue().pop(consumer_id, None)
            if _Debug:
                lg.out(_DebugLevel, 'message.do_read STOPPED consumer "%s", too much pending messages but no callbacks' % consumer_id)
            continue
        # filter messages which consumer is not interested in
        if cb_info['direction']:
            consumer_messages = filter(lambda msg: msg['dir'] == cb_info['direction'], pending_messages)
        else:
            consumer_messages = filter(None, pending_messages)
        if cb_info['message_types']:
            consumer_messages = filter(lambda msg: msg['type'] in cb_info['message_types'], consumer_messages)
        consumer_messages = list(consumer_messages)
        if not consumer_messages:
            message_queue()[consumer_id] = []
            continue
        # callback is a one-time Deferred object, must call now it and release the callback
        if isinstance(cb_info['callback'], Deferred):
            if cb_info['callback'].called:
                if _Debug:
                    lg.out(_DebugLevel, 'message.do_read %d messages waiting consuming by "%s", callback state is "called"' % (
                        len(message_queue()[consumer_id]), consumer_id))
                consumers_callbacks().pop(consumer_id, None)
                continue
            try:
                cb_info['callback'].callback(consumer_messages)
            except:
                lg.exc()
                consumers_callbacks().pop(consumer_id, None)
                continue
            consumers_callbacks().pop(consumer_id, None)
            message_queue()[consumer_id] = []
            total_consumed += len(consumer_messages)
            continue
        # callback is a "callable" method which we must not release
        message_queue()[consumer_id] = []
        try:
            ok = cb_info['callback'](consumer_messages)
        except:
            lg.exc()
            consumers_callbacks().pop(consumer_id, None)
            # put back failed messages to the queue so consumer can re-try
            message_queue()[consumer_id] = pending_messages
            continue
        if not ok:
            lg.err('failed consuming messages by consumer %r' % consumer_id)
            consumers_callbacks().pop(consumer_id, None)
            # put back failed messages to the queue so consumer can re-try
            message_queue()[consumer_id] = pending_messages
            continue
        total_consumed += len(consumer_messages)
    if _Debug:
        lg.args(_DebugLevel, total_consumed=total_consumed)
    return total_consumed
