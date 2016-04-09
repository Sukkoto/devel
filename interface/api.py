#!/usr/bin/python
#api.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: api

Here is a bunch of methods to interact with BitDust software.
"""

#------------------------------------------------------------------------------ 

_Debug = True

#------------------------------------------------------------------------------ 

import os

from twisted.internet.defer import Deferred, succeed

from services import driver

#------------------------------------------------------------------------------ 

def on_api_result_prepared(result):
    # TODO
    return result

#------------------------------------------------------------------------------ 

def OK(result='', message=None, status='OK',):
    o = {'status': status, 'result': result,}
    if message is not None:
        o['message'] = message
    o = on_api_result_prepared(o)
    return o

def RESULT(result=[], message=None, status='OK'):
    o = {'status': status, 'result': result,}
    if message is not None:
        o['message'] = message
    o = on_api_result_prepared(o)
    return o
            
def ERROR(errors=[], message=None, status='ERROR'):
    o = {'status': status,
         'errors': errors if isinstance(errors, list) else [errors,],}
    if message is not None:
        o['message'] = message
    o = on_api_result_prepared(o)
    return o

#------------------------------------------------------------------------------ 

def stop():
    """
    Stop the main process immediately.
    Return:
        "{'status': 'OK', 'result': 'stopped'}"
    """
    from logs import lg
    lg.out(2, 'api.stop sending event "stop" to the shutdowner() machine')
    from main import shutdowner
    shutdowner.A('stop', 'exit')
    return OK('stopped')
    

def restart(showgui=False):
    """
    Restart the main process, if flag show=True the GUI will be opened after restart.
    Return:
        "{'status': 'OK', 'result': 'restarted'}"
    """
    from logs import lg
    from main import shutdowner
    if showgui: 
        lg.out(2, 'api.restart forced for GUI, added param "show", sending event "stop" to the shutdowner() machine')
        shutdowner.A('stop', 'restartnshow')
        return OK('restarted with GUI')
    lg.out(2, 'api.restart did not found bpgui process nor forced for GUI, just do the restart, sending event "stop" to the shutdowner() machine')
    shutdowner.A('stop', 'restart')
    return OK('restarted')


def show():
    """
    Opens a default web browser to show the BitDust GUI.
    Return:
        "{'status': 'OK', 
          'result': '`show` event has been sent to the main process'}"
    """
    from logs import lg
    lg.out(4, 'api.show')
    from main import settings
    if settings.NewWebGUI():
        from web import control
        control.show()
    else:
        from web import webcontrol
        webcontrol.show()
    return OK('"show" event has been sent to the main process')

#------------------------------------------------------------------------------ 

def config_get(key, default=None):
    """
    Return current value for specific option.
    Return: 
        "{'status': 'OK',
          'result': [
             {'type': 'positive integer',
              'value': '8', 
              'key': 'logs/debug-level'}]}"    
    """
    from logs import lg
    lg.out(4, 'api.config_get [%s]' % key)
    from main import config
    if not config.conf().exist(key):
        return ERROR('option "%s" not exist' % key)
    return RESULT([{
        'key': key, 
        'value': config.conf().getData(key, default), 
        'type': config.conf().getTypeLabel(key),
        # 'code': config.conf().getType(key),
        # 'label': config.conf().getLabel(key),
        # 'info': config.conf().getInfo(key)
        }])
        
def config_set(key, value, typ=None):
    """
    Set a value for given option.
    Return: 
        "{'status': 'OK',
          'result': [
             {'type': 'positive integer',
              'old_value': '8',
              'value': '10',
              'key': 'logs/debug-level'}]}"
    """
    from logs import lg
    lg.out(4, 'api.config_set [%s]=%s' % (key, value))
    from main import config
    v = {}
    if config.conf().exist(key):
        v['old_value'] = config.conf().getData(key)
    if type in [ config.TYPE_STRING, 
                 config.TYPE_TEXT,
                 config.TYPE_UNDEFINED, ] or typ is None: 
        config.conf().setData(key, value)
    elif typ in [config.TYPE_BOOLEAN, ]:
        config.conf().setBool(key, value)
    elif typ in [config.TYPE_INTEGER, 
                 config.TYPE_POSITIVE_INTEGER, 
                 config.TYPE_NON_ZERO_POSITIVE_INTEGER, ]:
        config.conf().setInt(key, value)
    elif typ in [config.TYPE_FOLDER_PATH,
                 config.TYPE_FILE_PATH, 
                 config.TYPE_COMBO_BOX,
                 config.TYPE_PASSWORD,]:
        config.conf().setString(key, value)
    else:
        config.conf().setData(key, str(value))
    v.update({  'key': key, 
                'value': config.conf().getData(key), 
                'type': config.conf().getTypeLabel(key)
                # 'code': config.conf().getType(key),
                # 'label': config.conf().getLabel(key),
                # 'info': config.conf().getInfo(key), 
                })
    return RESULT([v,])

def config_list(sort=False):
    """
    Monitor all options and values.
    Return:
        "{'status': 'OK',
          'result': [
             {'type': 'boolean',
              'value': 'true',
              'key': 'services/backups/enabled'}, 
             {'type': 'boolean',
              'value': 'false',
              'key': 'services/backups/keep-local-copies-enabled'},
             {'type': 'disk space',
              'value': '128 MB',
              'key': 'services/backups/max-block-size'}]}"
    """
    from logs import lg
    lg.out(4, 'api.config_list')
    from main import config
    r = config.conf().cache()
    r = map(lambda key: {
        'key': key,
        'value': r[key],
        'type': config.conf().getTypeLabel(key)}, sorted(r.keys()))
    if sort:
        r = sorted(r, key=lambda i: i['key'])
    return RESULT(r) 

#------------------------------------------------------------------------------ 

def filemanager(json_request):
    """
    A method to execute calls from GUI front-end and interact with web browser.
    This is a special "gates" created only for Ajax calls from GUI - for 
    for specific file system io operations.
    
        request:
            {"params":{"mode":"stats"}}
        response:
            {'bytes_donated': 8589934592,
             'bytes_indexed': 43349475,
             'bytes_needed': 104857600,
             'bytes_used_supplier': 21738768,
             'bytes_used_total': 86955072,
             'customers': 0,
             'files_count': 5,
             'folders_count': 0,
             'items_count': 15,
             'max_suppliers': 4,
             'online_suppliers': 0,
             'suppliers': 4,
             'timestamp': 1458669668.288339,
             'value_donated': '8 GB',
             'value_needed': '100 MB',
             'value_used_total': '82.93 MB'}

    You can also access those methods with API alias:
        filemanager_{method name}()
    More info will be added soon.
    """
    from storage import filemanager_api
    return filemanager_api.process(json_request) 

#------------------------------------------------------------------------------ 

def backups_update():
    """
    A method to restart backup_monitor() Automat and 
    fire "synchronize" process with remote nodes.
    Return:
        "{'status': 'OK', 'result': 'the main loop has been restarted'}"
    """
    from storage import backup_monitor
    backup_monitor.A('restart') 
    from logs import lg
    lg.out(4, 'api.backups_update')
    return OK('the main loop has been restarted')


def backups_list():
    """
    Return a whole tree of files and folders in the catalog.
    Return:
        "{'status': 'OK', 
          'result': [
             {'path': '/Users/veselin/Documents', 
              'versions': [], 
              'type': 'parent', 
              'id': '0/0/1', 
              'size': 38992196}, 
             {'path': '/Users/veselin/Documents/python', 
              'versions': [], 
              'type': 'parent', 
              'id': '0/0/1/0', 
              'size': 5754439}, 
             {'path': '/Users/veselin/Documents/python/python27.chm', 
              'versions': [
                  {'version': 'F20160313043757PM', 
                   'blocks': 1, 
                   'size': '11 MB'}], 
              'type': 'file', 
              'id': '0/0/1/0/0', 
              'size': 5754439}]}"    
    """
    from storage import backup_fs
    from lib import diskspace
    from logs import lg
    result = []
    for pathID, localPath, item in backup_fs.IterateIDs():
        result.append({
            'id': pathID,
            'path': localPath,
            'type': backup_fs.TYPES.get(item.type, '').lower(),
            'size': item.size,
            'versions': map(
                lambda v: {
                   'version': v,
                   'blocks': max(0, item.versions[v][0]+1),
                   'size': diskspace.MakeStringFromBytes(max(0, item.versions[v][1])),},
                item.versions.keys())})
    lg.out(4, 'api.backups_list %s' % result)
    return RESULT(result)


def backups_id_list():
    """
    Return only list of items uploaded on remote machines.
    Return:
        "{'status': 'OK', 
          'result': [{'backupid': '0/0/1/0/0/F20160313043757PM', 
                      'path': '/Users/veselin/Documents/python/python27.chm', 
                      'size': '11 MB'}, 
                     {'backupid': '0/0/0/0/0/0/F20160315052257PM', 
                      'path': '/Users/veselin/Music/Bob Marley/01-Soul Rebels (1970)/01-Put It On.mp3', 
                      'size': '8.27 MB'}]}"        
    """
    from storage import backup_fs
    from contacts import contactsdb
    from lib import diskspace
    from logs import lg
    result = []
    for itemName, backupID, versionInfo, localPath in backup_fs.ListAllBackupIDsFull(True, True):
        if versionInfo[1] >= 0 and contactsdb.num_suppliers() > 0:
            szver = diskspace.MakeStringFromBytes(versionInfo[1]) + ' / ' + diskspace.MakeStringFromBytes(versionInfo[1]/contactsdb.num_suppliers()) 
        else:
            szver = '?'
        szver = diskspace.MakeStringFromBytes(versionInfo[1]) if versionInfo[1] >= 0 else '?'
        result.append({
            'backupid': backupID,
            'size': szver,
            'path': localPath, })
    lg.out(4, 'api.backups_id_list %s' % result)
    return RESULT(result)


def backup_start_id(pathID):
    """
    Start uploading a given item already existed in the catalog by its path ID.
    Return:
        "{'status': 'OK', 
          'result': 'uploading 0/0/1/0/0 started, local path is: /Users/veselin/Documents/python/python27.chm'}"
    """
    from system import bpio
    from storage import backup_fs
    from storage import backup_control
    from web import control
    from logs import lg
    local_path = backup_fs.ToPath(pathID)
    if local_path is not None:
        if bpio.pathExist(local_path):
            backup_control.StartSingle(pathID, local_path)
            backup_fs.Calculate()
            backup_control.Save()
            control.request_update([('pathID', pathID),])
            lg.out(4, 'api.backup_start_id %s OK!' % pathID)
            return OK('uploading %s started, local path is: %s' % (pathID, local_path))
    lg.out(4, 'api.backup_start_id %s not found' % pathID)
    return ERROR('item %s not found' % pathID)

    
def backup_start_path(path):
    """
    Start uploading file or folder to remote nodes, assign a new path ID and add it to the catalog.
    Return:
        "{'status': 'OK',
          'result': 'uploading 0/0/1/0/0 started, local path is: /Users/veselin/Documents/python/python27.chm'}"
    """
    from system import bpio
    from storage import backup_fs
    from storage import backup_control
    from web import control
    from logs import lg
    localPath = bpio.portablePath(unicode(path))
    if not bpio.pathExist(localPath):
        lg.out(4, 'api.backup_start_path local path %s not found' % path)
        return ERROR('local path %s not found' % path)
    result = ''
    pathID = backup_fs.ToID(localPath)
    if pathID is None:
        if bpio.pathIsDir(localPath):
            pathID, iter, iterID = backup_fs.AddDir(localPath, True)
            result += 'uploading %s started, ' % pathID
            result += 'new folder was added to catalog: %s, ' % localPath
        else:
            pathID, iter, iterID = backup_fs.AddFile(localPath, True)
            result += 'uploading %s started, ' % pathID
            result += 'new file was added to catalog: %s, ' % localPath
    else:
        result += 'uploading %s started, ' % pathID
        result += 'local path is: %s' % localPath
    backup_control.StartSingle(pathID, localPath)
    backup_fs.Calculate()
    backup_control.Save()
    control.request_update([('pathID', pathID),])
    lg.out(4, 'api.backup_start_path %s OK!' % path)
    return OK(result)

        
def backup_dir_add(dirpath):
    """
    Add given folder to the catalog but do not start uploading process.
    Return:
        "{'status': 'OK',
          'result': 'new folder was added: 0/0/2, local path is /Users/veselin/Movies/'}" 
    """
    from storage import backup_fs
    from storage import backup_control
    from system import dirsize
    from web import control
    newPathID, iter, iterID = backup_fs.AddDir(dirpath, True)
    dirsize.ask(dirpath, backup_control.OnFoundFolderSize, (newPathID, None))
    backup_fs.Calculate()
    backup_control.Save()
    control.request_update([('pathID', newPathID),])
    return OK('new folder was added: %s, local path is %s' % (newPathID, dirpath))


def backup_file_add(filepath):
    """  
    Add a single file to the catalog, skip uploading.
    Return:
        "{'status': 'OK', 'result': 'new file was added: 0/0/3/0, local path is /Users/veselin/Downloads/pytest-2.9.0.tar.gz'}"
    """ 
    from storage import backup_fs
    from storage import backup_control
    from web import control
    newPathID, iter, iterID = backup_fs.AddFile(filepath, True)
    backup_fs.Calculate()
    backup_control.Save()
    control.request_update([('pathID', newPathID),])
    return OK('new file was added: %s, local path is %s' % (newPathID, filepath))


def backup_tree_add(dirpath):
    """
    Recursively reads the entire folder and put files and folders items into the catalog,
    but did not start any uploads.
    Results:
        "{'status': 'OK',
          'result': '21 items were added to catalog, parent path ID is 0/0/1/2, root folder is /Users/veselin/Documents/reports'}"
    """
    from storage import backup_fs
    from storage import backup_control
    from web import control
    newPathID, iter, iterID, num = backup_fs.AddLocalPath(dirpath, True)
    backup_fs.Calculate()
    backup_control.Save()
    control.request_update([('pathID', newPathID),])
    if not newPathID:
        return ERROR('nothing was added to catalog')
    return OK('%d items were added to catalog, parent path ID is %s, root folder is %s' % (
        num, newPathID, dirpath))


def backup_delete_local(backupID):
    """
    Remove only local files belongs to this particular backup.
    All remote data stored on suppliers machines remains unchanged.
    Return:
        "{'status': 'OK',
          'result': '8 files were removed with total size of 16 Mb'}"
    """
    from storage import backup_fs
    from storage import backup_matrix
    from main import settings
    from web import control
    from logs import lg
    num, sz = backup_fs.DeleteLocalBackup(settings.getLocalBackupsDir(), backupID)
    lg.out(4, 'api.backup_delete_local %s : %d, %s' % (backupID, num, sz))
    backup_matrix.EraseBackupLocalInfo(backupID)
    backup_fs.Scan()
    backup_fs.Calculate()
    control.request_update([('backupID', backupID),])
    return OK("%d files were removed with total size of %s" % (num,sz))


def backup_delete_id(pathID_or_backupID):
    """
    Delete local and remote copies of given item in catalog.
    This will completely remove your data from BitDust network.
    You can specify either path ID of that location or specific version.
    Return:
        "{'status': 'OK',
          'result': 'version 0/0/1/1/0/F20160313043419PM was deleted from remote peers'}"
    """
    from storage import backup_fs
    from storage import backup_control
    from storage import backup_monitor
    from main import settings
    from web import control
    from lib import packetid
    from logs import lg
    if not packetid.Valid(pathID_or_backupID):
        lg.out(4, 'api.backup_delete_id invalid item %s' % pathID_or_backupID)
        return OK('invalid item id: %s' % pathID_or_backupID)
    version = None
    if packetid.IsBackupIDCorrect(pathID_or_backupID):
        pathID, version = packetid.SplitBackupID(pathID_or_backupID)
        backupID = pathID + '/' + version
    if version:
        result = backup_control.DeleteBackup(backupID, saveDB=False)
        if not result:
            lg.out(4, 'api.backup_delete_id not found %s' % backupID)
            return ERROR('item %s is not found in catalog' % backupID)
        backup_control.Save()
        backup_monitor.A('restart')
        control.request_update([('backupID', backupID),])
        lg.out(4, 'api.backup_delete_id %s was deleted' % pathID)
        return OK('version %s was deleted from remote peers' % backupID)
    pathID = pathID_or_backupID
    result = backup_control.DeletePathBackups(pathID, saveDB=False, calculate=False)
    if not result:
        lg.out(4, 'api.backup_delete_id not found %s' % pathID)
        return ERROR('item %s is not found in catalog' % pathID)
    backup_fs.DeleteLocalDir(settings.getLocalBackupsDir(), pathID)
    backup_fs.DeleteByID(pathID)
    backup_fs.Scan()
    backup_fs.Calculate()
    backup_control.Save()
    backup_monitor.A('restart')
    control.request_update([('pathID', pathID),])
    lg.out(4, 'api.backup_delete_id %s was deleted' % pathID)
    return OK('item %s was deleted from remote peers' % pathID)


def backup_delete_path(localPath):
    """
    Completely remove any data stored for given location from BitDust network.
    All data for given item will be removed from remote peers.
    Any local files related to this path will be removed as well.
    Return:
        "{'status': 'OK',
          'result': 'item 0/1/2 was deleted from remote peers'}"
    """
    from storage import backup_fs
    from storage import backup_control
    from storage import backup_monitor
    from main import settings
    from web import control
    from lib import packetid
    from system import bpio
    from logs import lg
    localPath = bpio.portablePath(unicode(localPath))
    lg.out(4, 'api.backup_delete_path %s' % localPath)
    pathID = backup_fs.ToID(localPath)
    if not pathID:
        lg.out(4, 'api.backup_delete_path %s not found' % localPath)
        return ERROR('path %s is not found in catalog' % localPath)
    if not packetid.Valid(pathID):
        lg.out(4, 'api.backup_delete_path invalid %s' % pathID)
        return ERROR('invalid pathID found %s' % pathID)
    result = backup_control.DeletePathBackups(pathID, saveDB=False, calculate=False)
    if not result:
        lg.out(4, 'api.backup_delete_path %s not found' % pathID)
        return ERROR('item %s is not found in catalog' % pathID)
    backup_fs.DeleteLocalDir(settings.getLocalBackupsDir(), pathID)
    backup_fs.DeleteByID(pathID)
    backup_fs.Scan()
    backup_fs.Calculate()
    backup_control.Save()
    backup_monitor.A('restart')
    control.request_update([('pathID', pathID),])
    lg.out(4, 'api.backup_delete_path %s was deleted' % pathID)
    return OK('item %s was deleted from remote peers' % pathID)
        

def restore_single(pathID_or_backupID_or_localPath, destinationPath=None):
    """
    Download data from remote peers to you local machine.
    You can use different methods to select the target data:
        + item ID in the catalog
        + full version identifier
        + local path
    It is possible to select the destination folder to extract requested files to.
    By default this method uses known location from catalog for given item.
    WARNING: Your existing local data will be overwritten.
    Return:
        "{'status': 'OK',
          'result': 'downloading of version 0/0/1/1/0/F20160313043419PM has been started to /Users/veselin/Downloads/restore/'}"
    """
    from storage import backup_fs
    from storage import backup_control
    from storage import restore_monitor
    from web import control
    from system import bpio
    from lib import packetid
    from logs import lg
    print pathID_or_backupID_or_localPath, destinationPath
    if not packetid.Valid(pathID_or_backupID_or_localPath):
        localPath = bpio.portablePath(unicode(pathID_or_backupID_or_localPath))
        pathID = backup_fs.ToID(localPath)
        if not pathID:
            lg.out(4, 'api.restore_single path %s not found' % localPath)
            return ERROR('path %s is not found in catalog' % localPath)
        item = backup_fs.GetByID(pathID)
        if not item:
            lg.out(4, 'api.restore_single item %s not found' % pathID)
            return ERROR('item %s is not found in catalog' % pathID)
        version = item.get_latest_version()
        backupID = pathID + '/' + version
    else:
        if packetid.IsBackupIDCorrect(pathID_or_backupID_or_localPath):
            pathID, version = packetid.SplitBackupID(pathID_or_backupID_or_localPath)
            backupID = pathID + '/' + version
        elif packetid.IsPathIDCorrect(pathID_or_backupID_or_localPath):
            pathID = pathID_or_backupID_or_localPath
            item = backup_fs.GetByID(pathID)
            if not item:
                lg.out(4, 'api.restore_single item %s not found' % pathID)
                return ERROR('path %s is not found in catalog' % pathID)
            version = item.get_latest_version()
            if not version:
                lg.out(4, 'api.restore_single not found versions %s' % pathID)
                return ERROR('not found any versions for %s' % pathID)
            backupID = pathID + '/' + version
        else:
            lg.out(4, 'api.restore_single %s not valid location' % pathID_or_backupID_or_localPath)
            return ERROR('not valid location')
    if backup_control.IsBackupInProcess(backupID):
        lg.out(4, 'api.restore_single %s in process' % backupID)
        return ERROR('download not possible, uploading %s is in process' % backupID)
    pathID, version = packetid.SplitBackupID(backupID)
    if backup_control.HasTask(pathID):
        lg.out(4, 'api.restore_single %s scheduled already' % pathID)
        return OK('downloading task for %s already scheduled' % pathID)
    localPath = backup_fs.ToPath(pathID)
    if not localPath:
        lg.out(4, 'api.restore_single %s not found' % pathID)
        return ERROR('location %s not found in catalog' % pathID)
    if destinationPath:
        if len(localPath) > 3 and localPath[1] == ':' and localPath[2] == '/':
            # TODO: - also may need to check other options like network drive (//) or so 
            localPath = localPath[3:]
        localDir = os.path.dirname(localPath.lstrip('/'))
        restoreDir = os.path.join(destinationPath, localDir)
        restore_monitor.Start(backupID, restoreDir)
        control.request_update([('pathID', pathID),])
    else:
        restoreDir = os.path.dirname(localPath)
        restore_monitor.Start(backupID, restoreDir) 
        control.request_update([('pathID', pathID),])
    lg.out(4, 'api.restore_single %s OK!' % backupID)
    return OK('downloading of version %s has been started to %s' % (backupID, restoreDir))

#------------------------------------------------------------------------------ 

def list_messages():
    """
    """
    if not driver.is_started('service_private_messages'):
        return { 'result': 'service_private_messages() is not started', }
    from chat import message
    mlist = [{},] #TODO: just need some good idea to keep messages synchronized!!!
    return RESULT(mlist)
    
    
def send_message(recipient, message_body):
    """
    Send a message to remote peer.
    Return: 
        {'result': 'message to http://p2p-id.ru/alice.xml was sent', 
         'packet': ... , 
         'recipient': http://p2p-id.ru/alice.xml,
         'message': 'Hi Alice!!!',
         'error': '',}
    """
    if not driver.is_started('service_private_messages'):
        return { 'result': 'failed sending message to %s' % recipient,
                 'recipient': recipient,
                 'message': message_body,
                 'error': 'service_private_messages() is not started', }
    from chat import message
    recipient = str(recipient)
    if not recipient.startswith('http://'):
        from contacts import contactsdb
        recipient = contactsdb.find_correspondent_by_nickname(recipient) or recipient
    result = message.SendMessage(recipient, message_body)
    if isinstance(result, Deferred):
        ret = Deferred()
        result.addCallback(lambda packet: ret.callback({
            'result': 'message to %s was sent' % recipient,
            'packet': packet.outpacket,
            'recipient': recipient,
            'message': message_body,
            'error': '',}))
        result.addErrback(lambda err: ret.callback({
            'result': 'failed sending message to %s' % recipient,
            'recipient': recipient,
            'message': message_body,
            'error': err}))
        return ret
    return {'result': 'message to %s was sent' % recipient, 
            'packet': result.outpacket, 
            'recipient': recipient,
            'message': message_body,
            'error': '', }
    
#------------------------------------------------------------------------------ 

def list_correspondents():
    """
    Return a list of your friends.
    Return:
        [ {'idurl': 'http://p2p-id.ru/alice.xml', 
           'nickname': 'alice'}, 
          {'idurl': 'http://p2p-id.ru/bob.xml', 
           'nickname': 'bob'},]
    """
    from contacts import contactsdb
    return { 'result': map(lambda v: {
                'idurl': v[0],
                'nickname': v[1],},
              contactsdb.correspondents()), } 
    
    
def add_correspondent(idurl, nickname=''):
    from contacts import contactsdb
    contactsdb.add_correspondent(idurl, nickname)
    contactsdb.save_correspondents()
    return { 'result': 'new correspondent was added',
             'nickname': nickname,
             'idurl': idurl, }
    

def remove_correspondent(idurl):
    from contacts import contactsdb
    result = contactsdb.remove_correspondent(idurl)
    contactsdb.save_correspondents()
    if result:
        result = 'correspondent %s was removed'
    else:
        result = 'correspondent %s was not found'
    return { 'result': result, }


def find_peer_by_nickname(nickname):
    from twisted.internet.defer import Deferred
    from chat import nickname_observer
    nickname_observer.stop_all()
    d = Deferred()
    def _result(result, nik, pos, idurl):
        return d.callback({'result':
            { 'result': result,
              'nickname': nik,
              'position': pos,
              'idurl': idurl,}})        
    nickname_observer.find_one(nickname, 
        results_callback=_result)
    # nickname_observer.observe_many(nickname, 
        # results_callback=lambda result, nik, idurl: d.callback((result, nik, idurl)))
    return d

#------------------------------------------------------------------------------ 

def ping(idurl, timeout=10):
    """
    The "ping" command performs following actions:
    1. Request remote identity source by idurl,
    2. Send my Identity to remote contact addresses, taken from identity,
    3. Wait first Ack packet from remote peer,
    4. Failed by timeout or identity fetching error.
    Return:
        "{'status': 'OK', 
          'result': '(signed.Packet[Ack(Identity) bob|bob for alice], in_70_19828906(DONE))'}"
    """
    if not driver.is_started('service_identity_propagate'):
        return succeed(ERROR('service_identity_propagate() is not started'))
    from p2p import propagate
    result = Deferred()
    d = propagate.PingContact(idurl, int(timeout)) 
    d.addCallback(
        lambda resp: result.callback(
            OK([str(resp),])))
    d.addErrback(
        lambda err: result.callback(
            ERROR(err.getErrorMessage())))
    return result
    
#------------------------------------------------------------------------------ 


