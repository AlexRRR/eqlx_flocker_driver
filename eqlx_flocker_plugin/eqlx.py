from flocker.node.agents.blockdevice import (
    VolumeException, AlreadyAttachedVolume,
    UnknownVolume, UnattachedVolume,
    IBlockDeviceAPI, BlockDeviceVolume
)
from zope.interface import implementer, Interface
import paramiko
import time
import functools
import random
import eventlet
from eventlet import greenthread
import greenlet
import pdb
import socket
import re
import uuid
from subprocess import check_output
from eliot import Message
from bitmath import Byte, GiB
from twisted.python.filepath import FilePath

class VolumeBackendAPIException(Exception):
    """
    Exception from backed mgmt server
    """

class Eqlx(object):

    def __init__(self, eqlx_id, eqlx_ip, username, password ):
        self.eqlx_id = eqlx_id
        self.eqlx_ip = eqlx_ip
        self.username = username
        self.password = password
        self.ssh = self._conn()
        self._init_terminal()

    def _init_terminal(self):
        chan = self.ssh.invoke_shell()
        out = self.get_output(chan)
        stty = 'stty columns 255'
        chan.send(stty + '\r')
        self.get_output(chan)


    def _conn(self):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(self.eqlx_ip,username=self.username,password=self.password)
            return ssh
        except :
            return None


    def get_output(self, chan, ending_str=None):
        out = ''
        ending = '%s> ' % (self.eqlx_id)
        std_ending = '%s> ' % (self.eqlx_id)
        test = '> '
        if ending_str is not None:
            ending = '%s%s> ' % (self.eqlx_id, '({0})'.format(ending_str))
        while (out.find(test) == -1):
            ret = chan.recv(102400)
            if len(ret) == 0:
                msg = ("The EQL array has closed the connection.")
                raise VolumeBackendAPIException(msg)
            out += ret

        output = out.splitlines()
        self.check_output(output)
        return output


    def with_timeout(f):
        @functools.wraps(f)
        def __inner(self, *args, **kwargs):
            timeout = kwargs.pop('timeout', None)
            gt = eventlet.spawn(f, self, *args, **kwargs)
            if timeout is None:
                return gt.wait()
            else:
                kill_thread = eventlet.spawn_after(timeout, gt.kill)
                try:
                    res = gt.wait()
                except greenlet.GreenletExit:
                    raise VolumeBackendAPIException("Command timed out")
                else:
                    kill_thread.cancel()
                    return res
        return __inner

    def check_output(self ,out):
        if any(ln.startswith(('% Error', 'Error:')) for ln in out):
            desc = ("Error executing EQL command")
            cmdout = '\n'.join(out)
            raise VolumeBackendAPIException(cmdout)

    @with_timeout
    def send_command(self, cmd, ending_str=None):
        chan = self.ssh.invoke_shell()
        self.get_output(chan)
        chan.send(cmd + '\r')
        return self.get_output(chan)

    @with_timeout
    def delete_volume(self, blockdevice_id, ending_str=None):
        chan = self.ssh.invoke_shell()
        self.get_output(chan)
        cmd = 'cli-settings confirmation off'
        chan.send(cmd + '\r')
        self.get_output(chan, ending_str=None)
        try:
            cmd = 'volume select %s' % blockdevice_id
            chan.send(cmd + '\r')
            self.get_output(chan,ending_str='volume_%s' % blockdevice_id)
        except VolumeBackendAPIException as exc:
            raise UnknownVolume(blockdevice_id)
        cmd = 'offline'
        chan.send(cmd + '\r')
        self.get_output(chan,ending_str='volume_%s' % blockdevice_id)
        cmd = 'exit'
        chan.send(cmd + '\r')
        self.get_output(chan,ending_str=None)
        cmd = 'volume delete %s' % blockdevice_id
        chan.send(cmd + '\r')
        self.get_output(chan, ending_str=None)

    @with_timeout
    def allow_volume(self, dataset_id, ip_address, ending_str=None):
        chan = self.ssh.invoke_shell()
        self.get_output(chan)
        cmd = 'cli-settings confirmation off'
        chan.send(cmd + '\r')
        self.get_output(chan, ending_str=None)
        try:
            cmd = 'volume select %s' % dataset_id
            chan.send(cmd + '\r')
            self.get_output(chan,ending_str='volume_%s' % dataset_id)
        except VolumeBackendAPIException as exc:
            raise UnknownVolume(dataset_id)
        cmd = 'access create ipaddress %s' % ip_address
        chan.send(cmd + '\r')
        self.get_output(chan,ending_str='volume_%s' % dataset_id)
        cmd = 'exit'
        chan.send(cmd + '\r')
        self.get_output(chan,ending_str=None)

    def iscsi_login(self, blockdevice_id):
         check_output([b"/usr/bin/iscsiadm","-m","discoverydb","-t","sendtargets", "-p", self.eqlx_ip, "--discover"])
         iscsi_name = self.iscsi_name_from_dataset_id(blockdevice_id) 
	 output = check_output([b"/usr/bin/iscsiadm","-m","node","--targetname", iscsi_name, "--login"])
	

    def _extract_value(self, info_string, expect, index):
        data = info_string[index]
        tokenized = data.split(": ")
        if tokenized[0] == expect:
            return ''.join(tokenized[1:]).strip()
        else:
            raise UnknownVolume('value not found')

    @with_timeout
    def _cli_settings(self):
        chan = self.ssh.invoke_shell()
        self.get_output(chan)
        cmd = 'cli-settings formatoutput off'
        chan.send(cmd + '\r')
        self.get_output(chan, ending_str=None)
        cmd = 'cli-settings paging off'
        chan.send(cmd + '\r')
        self.get_output(chan, ending_str=None)
        return chan

    @with_timeout
    def iscsi_name_from_dataset_id(self, dataset_id):
        chan = self._cli_settings()
        try:
            cmd = 'volume show %s' % dataset_id
            chan.send(cmd + '\r')
            output = self.get_output(chan,ending_str='volume_%s' % dataset_id)
            iscsi_name = self._extract_value(output, 'iSCSI Name', 8)
            #if name trailed into next line
            if "ActualMembers" not in output[9]:
                iscsi_name += output[9]
            return iscsi_name
        except VolumeBackendAPIException as exc:
            raise UnknownVolume(dataset_id)

    @with_timeout
    def volume_info(self, blockdevice_id):
        chan = self._cli_settings()
        try:
            cmd = 'volume show %s' % blockdevice_id
            chan.send(cmd + '\r')
            output = self.get_output(chan,ending_str='volume_%s' % blockdevice_id)
            blockdevice_id = (u"%s" % self._extract_value(output, 'Name', 2))
            dataset_id = uuid.UUID("-".join(blockdevice_id.split("-")[1:]))
            size = int(self._extract_value(output, 'Size', 3).replace('GB',''))
            connection = self._extract_value(output, 'Connections', 19)
            attached_to = None
            if int(connection) > 0:
                attached_to = re.findall( r'[0-9]+(?:\.[0-9]+){3}', output[58] ).pop()
            volume = BlockDeviceVolume(size=size,
                                       attached_to=attached_to,
                                       blockdevice_id=blockdevice_id,
                                       dataset_id=dataset_id)
            return volume
        except VolumeBackendAPIException as exc:
            raise UnknownVolume(blockdevice_id)

    @with_timeout
    def list_volumes(self):
        chan = self._cli_settings()
        cmd = 'volume show -volume'
        volumes = []
        volume_list = self.send_command(cmd)
        previous = []
        VOL_SEGMENT_SIZE = 7
        first_segment = True
        ending_str = '%s>' % (self.eqlx_id)


        def blockdevice_from_segment(segment):
            blockdevice_id,size,snapshots,status,permission,connections,t = segment
            dataset_id = uuid.UUID("-".join(blockdevice_id.split("-")[1:]))
            return BlockDeviceVolume(size=int(re.findall(r'^\d+', size)[-1]),
                                    attached_to=None,
                                    dataset_id=dataset_id,
                                    blockdevice_id=u'{0}'.format(blockdevice_id))

        def append_only_volumes_from_cluster(previous):
            if (previous[0].startswith('flk')):
                current_vol = blockdevice_from_segment(previous)
                volumes.append(current_vol)
                print("appending: %s:" % previous[0])
            else:
               #print("skipping: %s" % previous[0])
               None

        for v in volume_list[3:]:
            try:
                segments = v.split()
                if (len(segments) == VOL_SEGMENT_SIZE and first_segment):
                    previous = segments
                    first_segment = False
                elif (len(segments) == VOL_SEGMENT_SIZE):
                    append_only_volumes_from_cluster(previous)
                    previous = segments
                elif (len(segments) == 1):
                    #ending line add last volume
                    if (ending_str in segments):
                        append_only_volumes_from_cluster(previous)
                    previous[0] = previous[0] + segments[0]
                    first_segment = False
            except ValueError as e:
                raise VolumeBackendAPIException(e)
        return volumes

    def _blockdevicevolume_from_dataset_id(self, dataset_id, size,
                                       attached_to=None):
        """
        Create a new ``BlockDeviceVolume`` with a ``blockdevice_id`` derived
        from the given ``dataset_id``.
        This is for convenience of implementation of the loopback backend (to
        avoid needing a separate data store for mapping dataset ids to block
        device ids and back again).
        Parameters accepted have the same meaning as the attributes of
        ``BlockDeviceVolume``.
        """
        return BlockDeviceVolume(
            size=size, attached_to=attached_to,
            dataset_id=dataset_id, blockdevice_id=u"flk-{0}".format(dataset_id),
        )

@implementer(IBlockDeviceAPI)
class EqlxBlockDeviceAPI(object):
    """
    Interfaces with Equallogic Block devices
    """
    def __init__ (self, cluster_id, eqlx_ip, compute_instance_id, username, password):
        self._cluster_id = cluster_id
        self._compute_instance_id = u'{0}'.format(compute_instance_id)
        self.eqlx_con = Eqlx("EQL-INX", eqlx_ip, username, password)

    def allocation_unit(self):
        """
        Increments of GBs only;
        """
        return int(1)

    def compute_instance_id(self):
        """
        :return: Compute instance id
        """
        return self._compute_instance_id

    def create_volume(self, dataset_id,size):
        """
        stub
        """
        volume = self.eqlx_con._blockdevicevolume_from_dataset_id(
                        size=size,
                        dataset_id=dataset_id)
        command = "vol create flk-%s %sGB %s" % (dataset_id, size, "thin-provision")
        self.eqlx_con.send_command(command, timeout=10)
        return volume


    def attach_volume(self, blockdevice_id, attach_to):
        """
        Attach ``blockdevice_id`` to the node indicated by ``attach_to``.

        :param unicode blockdevice_id: The unique identifier for the block
            device being attached.
        :param unicode attach_to: An identifier like the one returned by the
            ``compute_instance_id`` method indicating the node to which to
            attach the volume.

        :raises UnknownVolume: If the supplied ``blockdevice_id`` does not
            exist.
        :raises AlreadyAttachedVolume: If the supplied ``blockdevice_id`` is
            already attached.

        :returns: A ``BlockDeviceVolume`` with a ``attached_to`` attribute set
            to ``attach_to``.
        """
        current_vol = self.eqlx_con.volume_info(blockdevice_id)
        if current_vol.attached_to != None:
            raise AlreadyAttachedVolume('attached to %s' % current_vol.attach_to)
        self.eqlx_con.allow_volume(blockdevice_id,attach_to)
        self.eqlx_con.iscsi_login(blockdevice_id)
        current_vol.set(attached_to=unicode(attach_to))
        return current_vol



    def destroy_volume(self, blockdevice_id):
        """
        Destroy an existing volume.

        :param unicode blockdevice_id: The unique identifier for the volume to
            destroy.

        :raises UnknownVolume: If the supplied ``blockdevice_id`` does not
            exist.

        :return: ``None``
        """
        self.eqlx_con.delete_volume(blockdevice_id)


    def list_volumes(self):
        """
        List all the block devices available via the back end API.

        Only volumes for this particular Flocker cluster should be included.

        Make sure you can list large numbers of volumes. E.g. some cloud
        APIs have a hard limit on how many volumes they include in a
        result, and therefore require the use of paging to get all volumes
        listed.

        :returns: A ``list`` of ``BlockDeviceVolume``s.
        """
        return self.eqlx_con.list_volumes()

    def get_device_path(self, blockdevice_id):
        """
        Return the device path that has been allocated to the block device on
        the host to which it is currently attached.

        Returning the wrong value here can lead to data loss or corruption
        if a container is started with an unexpected volume. Make very
        sure you are returning the correct result.

        :param unicode blockdevice_id: The unique identifier for the block
            device.
        :raises UnknownVolume: If the supplied ``blockdevice_id`` does not
            exist.
        :raises UnattachedVolume: If the supplied ``blockdevice_id`` is
            not attached to a host.
        :returns: A ``FilePath`` for the device.
        """
        iscsi_name = self.eqlx_con.iscsi_name_from_dataset_id(blockdevice_id)
        output = check_output([b"/usr/bin/lsscsi","-t"])
        if str(blockdevice_id) not in output:
            raise UnattachedVolume(blockdevice_id)
        for device_entry in output.split("\n"):
            if str(blockdevice_id) in device_entry:
                dev = device_entry.split().pop()
                return FilePath(dev)

    def detach_volume(self, blockdevice_id):
         """
         Use for testing only
         """
         print("goooo")
