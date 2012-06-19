# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (C) 2011 Hewlett-Packard Development Company, L.P.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Interface to Nova and Euca tools for system tests.
"""
import boto
import euca2ools
import random
import time
import os
import os.path
from paramiko import SSHException
from instance_ssh_tools import load_ssh_key_from_file,    \
                               load_ssh_key_from_keypair, \
                               generate_keypair_files,    \
                               setup_ssh_connection


try:
    import novaclient.v1_1
    novaclient_version = 'V1.1'
except:
    import novaclient
    novaclient_version = 'V1.0'


#
# These multiline strings are python scripts that are injected onto VM
# instances to test volumes, and snapshots, on the instances. They are placed
# here, at the head of the file, because they cannot be indented in line with
# the functions where they are used. This makes the functions where theses
# multiline strings are used more readable.
#
WRITE_PATTERN_SCRIPT = """
#!/usr/bin/env python
import os
fd = os.open('{device}', os.O_RDWR)
size = os.lseek(fd, 0, os.SEEK_END)
os.lseek(fd, 0, os.SEEK_SET)
data = ''.join(chr((i + {key_value}) % 255) for i in xrange(4096))
for i in xrange(int((size / 4096) / (float(100)/{percentage_value}))):
    os.write(fd, data)
"""

CHECK_PATTERN_SCRIPT = """
#!/usr/bin/env python
import os
check_str = ''.join(chr((i + {key_value}) % 255) for i in xrange(4096))
result_str = "Pass"
fd = os.open('{device}', os.O_RDONLY)
size = os.lseek(fd, 0, os.SEEK_END)
os.lseek(fd, 0, os.SEEK_SET)
for i in xrange(int((size / 4096) / (float(100)/{percentage_value}))):
    tst_str = os.read(fd, 4096)
    if len(tst_str) == 4096 and tst_str != check_str:
        result_str = "Fail sector %d of %d" % (i, size / 4096)
        break
print result_str
"""

CHECK_MOUNT_VOLUME = """
#!/usr/bin/env python
import os
import subprocess
res_str = 'Fail'
mnt_dir = '/tmp/bocktest_mnt'
if os.path.isdir(mnt_dir) == False:
    os.makedirs(mnt_dir)
try:
    subprocess.check_call(['mount', '{device}', mnt_dir])
    subprocess.check_call(['umount', mnt_dir])
    os.rmdir(mnt_dir)
    mount_status = 1
    res_str = 'Pass'
except:
    res_str = 'Fail'

print res_str
"""

class EucaConnection(object):
    """
    Implements a connection to the Euca API
    """
    def __init__(self):
        """
        Initialise the objcet
        """
        self.eucahandle = euca2ools.Euca2ool('ao:x:', compat=True)
        self.euca = self.eucahandle.make_connection()

    def get_runnable_images(self):
        """
        Get a list of the runnable images in the nova installation.
        """
        retry_limit = os.environ.get('NOVA_VOLUME_TEST_RETRY_LIMIT', 3)

        #
        # This call to the euca api fails occasionally, so make a few
        # attempts before giving up.
        #
        for n in xrange(retry_limit):
            try:
                image_list = [image for image in self.euca.get_all_images() if
                                                (image.type == 'machine') and
                                                (image.kernel_id != None)]
            except boto.exception.EC2ResponseError:
                if n >= retry_limit - 1:
                    raise
                print "Got an EC2 error, try again to get list of images "

        return image_list

    def get_default_zone(self):
        """
        Get the first availability zone on this nova instance
        """
        #FIXME: Clearly this should query the system
        return "nova"


class Instance(object):
    """
    Class representing an instance of a Nova VM
    """
    def __init__(self):
        """
        Create a new instance
        """
        # Create a short random tag to add to our keypair name so we hopefully
        # don't collide with anybody else running the testsuite under the same
        # nova account

        key_random_tag = range(9)
        random.shuffle(key_random_tag)
        key_random_tag = "".join([str(i) for i in key_random_tag[:5]])
        self.keypair_name = "testsuite_" + key_random_tag

        print("Using keypair name: %s" % self.keypair_name)

        self.ec2 = EucaConnection()
        self.keypair = self.ec2.euca.create_key_pair(self.keypair_name)

        keyfile = '%s.priv' % self.keypair_name

        with open(keyfile, 'w') as fd:
            os.chmod(keyfile, 0600)
            fd.write(self.keypair.material)

        self.key = load_ssh_key_from_file(keyfile)

        images = self.ec2.get_runnable_images()
        preferred_images = ['Oneiric', 'Natty', 'natty_server_uec']

        self.image = None
        for preference in preferred_images:
            if self.image != None:
                break
            for image in images:
                if preference in image.displayName:
                    self.image = image
                    break

        if image != None:
            self.image = image
        else:
            self.image = images[0]

        print "Using image %s" % self.image.displayName

        # FIXME Automatic flavor selection requires using the nova api since
        # the euca api doesn't appear to support enumerating the available
        # flavors.
        # self.flavor = self.get_flavor()
        self.flavor = "standard.small"

        print "Using image %s on instance type %s" % (self.image, self.flavor)

        self.reservation = self.ec2.euca.run_instances(self.image.id,
                                                   min_count=1,
                                                   max_count=1,
                                                   key_name=self.keypair_name,
                                                   instance_type=self.flavor)

        self.instance = self.reservation.instances[0]
        self.id = self.instance.id
        self.sshclient = None

        self._free_devices = ["/dev/vd" + chr(d) for d in
                                            range(ord('g'), ord('z'))]
        #FIXME: Can we check what devices are actually free?

        print "Waiting for instance %s to start" % self.id
        while self.status() == "pending":
            time.sleep(2)

        self.public_ip = self._get_public_ip_address()

        print "Waiting for instance %s to boot" % self.id
        self.wait_for_console_shows_booted()

        print "Waiting 30 seconds for ssh to be started"
        time.sleep(60)
        self.sshclient = setup_ssh_connection(ip=self.public_ip, key=self.key)


    def get_flavor(self):
        """
        Select a VM flavor to use. If the environment variable
        NOVA_VOLUME_TEST_FLAVOR has been set use that, otherwise default to
        standard.large.
        Then check that the selected flavor is available, if not, use the first
        available flavor.
        Note that there doesn't seem to be a way to list flavours (aka instance
        types) with euca, so we're using the nova interface...
        """
        flavor_names = []
        if novaclient_version == 'V1.1':
            #
            # Since we have nova client V1.1 get the list of flavors available.
            #
            nova = novaclient.v1_1.Client(os.environ['NOVA_USERNAME'],
                                          os.environ['NOVA_API_KEY'],
                                          os.environ['NOVA_PROJECT_ID'],
                                          os.environ['NOVA_URL'])
            flavor_list = nova.flavors.list()
            flavor_names = [flavor.name for flavor in flavor_list]

        desired_flavor = os.environ.get('NOVA_VOLUME_TEST_FLAVOR',
                                        'standard.small')
        # Now check that the flavor we've selected is one of the available
        # flavors, and if not take the first available flavor.
        if len(flavor_names) > 0 and desired_flavor not in flavor_names:
            print ("Warning flavor %s is not available, using %s" %
                   (desired_flavor, flavor_names[0]))
            desired_flavor = flavor_names[0]
        return desired_flavor

    def wait_for_console_shows_booted(self, pollcount=30, sleeptime=10):
        """
        Loop waiting for the console log to indicate that the VM instance has
        completed its boot process.
        """
        for attempt in range(1, pollcount):
            cons = self.ec2.euca.get_console_output(self.instance)
            if 'system completely up' in cons.output or \
                            'cloud-init boot finished' in cons.output:
                return
            time.sleep(sleeptime)
        print "Failed to detect booting, Console output: "
        print cons.output
        raise Exception("Instance did not boot in %d seconds" %
                        (pollcount * sleeptime))

    def _get_public_ip_address(self):
        """
        Get a public IP address, if one is available.
        """
        public_ip = None
        try:
            ip_addr = self.ec2.euca.allocate_address()
            print "Using public IP address %s" % ip_addr.public_ip
            self.ec2.euca.associate_address(self.id, ip_addr.public_ip)
        except boto.exception.EC2ResponseError:
            print "Could not associate public IP addr with %s" % self.id
            return
        public_ip = ip_addr.public_ip
        # Must update self.instance because we have changed some of the
        # internal data.
        self.reservation = self.ec2.euca.get_all_instances([self.id])
        self.instance = self.reservation[0].instances[0]
        return public_ip

    def copy_file(self, fname, file_txt):
        """
        Push a file onto the instance with the given file name and containing
        the text supplied.
        """
        cmd = "/bin/cat << EOF > " + fname + " " + file_txt + "\nEOF"
        stdin, stdout, stderr = self.sshclient.exec_command(cmd)

    def run_python_file(self, fname):
        """
        Run a python file on the target instance.
        """
        # Use sudo since we will be accessing raw devices. If we are connected
        # as root then sudo will silently just work, and if we are connected
        # as user ubuntu then passwordless ssh should be enabled.

        # FIXME: spot sudo prompts / errors and raise an exception
        # FIXME: check nothing gets printed to stderr, if anything does then
        #        raise an exception
        cmd = "sudo /usr/bin/python " + fname
        stdin, stdout, stderr = self.sshclient.exec_command(cmd)
        out_str = stdout.read().strip()
        return out_str

    def status(self):
        """
        Return the status of the VM instance.
        """
        self.instance = \
                self.ec2.euca.get_all_instances([self.id])[0].  instances[0]
        return self.instance.state.split()[0]

    def next_device(self):
        """
        Get the next available device for the list of free devices.
        """
        return self._free_devices.pop()

    def delete(self):
        """
        Terminate and destroy this instance
        """
        print "Terminating instance:", str(self.instance)

        if self.public_ip != None:
            self.ec2.euca.disassociate_address(self.public_ip)
            self.ec2.euca.release_address(self.public_ip)
            self.public_ip = None
        self.ec2.euca.terminate_instances(str(self.instance))
        self.ec2.euca.delete_key_pair(str(self.keypair_name))
        if os.path.isfile('%s.priv' % self.keypair_name):
            os.unlink('%s.priv' % self.keypair_name)


class Volume(object):
    """
    Class representing a Nova Volume
    """
    def __init__(self, zone=None, size=None, snapshot=None, volume_id=None):
        """
        Create a volume, either empty of the specified size or from the
        specified snapshot
        """
        # One and only one of the parameters size, snapshot and volume_id must
        # be non None
        if len([p for p in [size, snapshot, volume_id] if p is not None]) != 1:
            raise Exception("Usage: one and only one of size, snapshot and "
                            "volume_id must be specified")

        self.ec2 = EucaConnection()

        if zone == None:
            zone = self.ec2.get_default_zone()
        snapid = None
        if volume_id == None:
            if snapshot != None:
                snapid = snapshot.id

            self.volume = self.ec2.euca.create_volume(size=size,
                                                      zone=zone,
                                                      snapshot=snapid)
            print "Waiting for volume", self.volume.id, "to be created"

            while self.status() == "creating":
                time.sleep(1)
        else:
            self.volume = \
                    self.ec2.euca.get_all_volumes(volume_ids=volume_id)[0]

        self.id = self.volume.id
        self._attached = False
        self.instance = None
        self.dev_name = ""

    def status(self):
        """
        Return the status of the Nova volume.
        """
        volume = self.ec2.euca.get_all_volumes([self.volume.id])[0]
        return volume.status.split()[0]

    def attached(self, instance=None):
        """
        Check if this volume is attached. If an instance is supplied, check
        that it is attached to said instance
        """
        if not self._attached:
            return False

        if not instance:
            return True

        if not self.instance == instance:
            return False

        return True

    def write_test_pattern(self, percentage=0, key=0):
        """
        Write a test pattern to the volume.

        If a percentage is specified, only write that much of the disk.

        If a key is supplied, generate the test pattern from that key, so that
        test patterns can be differentiated

        Volume must be attached.
        """

        if not self.attached():
            Exception("Usage: volume must be attached to write a test pattern")

        if percentage == 0:
            percentage = os.environ.get('NOVA_VOLUME_TEST_USE_PERCENTAGE', 100)

        file_txt = WRITE_PATTERN_SCRIPT.format(key_value=key,
                                               device=self.dev_name,
                                               percentage_value=percentage)

        self.instance.copy_file("write_pattern.py", file_txt)
        self.instance.run_python_file("write_pattern.py")

    def check_test_pattern(self, percentage=0, key=0):
        """
        Check a test pattern previously written to the volume.

        If a percentage is specified, only check that much of the disk.

        If a key is supplied, generate the test pattern from that key, so that
        test patterns can be differentiated

        Volume must be attached.
        """

        if not self.attached():
            Exception("Usage: volume must be attached to check a test pattern")

        if percentage == 0:
            percentage = os.environ.get('NOVA_VOLUME_TEST_USE_PERCENTAGE', 100)

        file_txt = CHECK_PATTERN_SCRIPT.format(key_value=key,
                                               device=self.dev_name,
                                               percentage_value=percentage)

        self.instance.copy_file("check_pattern.py", file_txt)
        out_str = self.instance.run_python_file("check_pattern.py")
        if out_str == 'Pass':
            return True
        else:
            return False

    def check_mount_device(self):
        """
        Check that the volume can be mounted.
        """

        if not self.attached():
            Exception("Usage: volume must be attached to attempt to mount it")

        file_txt = CHECK_MOUNT_VOLUME.format(device=self.dev_name)

        self.instance.copy_file("check_mount_volume.py", file_txt)
        out_str = self.instance.run_python_file("check_mount_volume.py")
        print "check_mount_device got result : <%s>" % (out_str)
        if out_str == 'Pass':
            return True
        else:
            return False

    def _get_dev_names(self):
        """
        Get the list of devices on the current instance.
        """

        cmd = "/bin/cat /proc/partitions"
        stdin, stdout, stderr = self.instance.sshclient.exec_command(cmd)
        out = stdout.read()
        devs = []
        for line in out.splitlines():
            words = line.split()
            if len(words) > 2:
                if words[3] == 'name':
                    continue
                devs.append('/dev/%s' % words[3])
        return devs

    def attach(self, instance):
        """
        Attempt to attach to the specified instance
        """
        if self.attached():
            Exception("attach: volume %s is already attached", self.id)

        self.instance = instance
        volume_id = self.id
        instance_id = instance.id
        device = instance.next_device()
        devs_before = self._get_dev_names()
        print "Attaching volume:", volume_id, "status:", self.status()
        print "to instance:", instance_id, "Using device:", device
        self.ec2.euca.attach_volume(volume_id, instance_id, device)

        print "Waiting for volume", volume_id, "to be attached to instance", \
                instance_id
        while self.status() != "in-use":
            time.sleep(1)

        devs_after = self._get_dev_names()

        if len(devs_after) != len(devs_before) + 1:
            Exception("attach(): Failed to detect attached device.")
        self.dev_name = [d for d in devs_after if d not in devs_before][0]
        print("Volume %s attached as %s" % (volume_id, self.dev_name))
        self._attached = True
        self.instance = instance

    def detach(self):
        """
        Attempt to detach from the specified instance
        """
        if self.instance == None:
            Exception("detach: no instance available.")

        volume_id = self.id
        instance_id = self.instance.id
        self.ec2.euca.detach_volume(volume_id, instance_id, True)

        print "Waiting for volume", volume_id, \
                "to be detached from instance", instance_id
        while self.status() == "in-use":
            time.sleep(1)
        self._attached = False

    def delete(self):
        """
        Destroy this volume.

        Volume must be detached.
        """
        if self.attached() == True:
            self.detach()

        retry_limit = os.environ.get('NOVA_VOLUME_TEST_RETRY_LIMIT', 3)
        #
        # This call to the euca api fails occasionally, so make a few
        # attempts before giving up.
        #
        print "delete volume %s" % self.id
        for n in xrange(retry_limit):
            try:
                self.ec2.euca.delete_volume(self.id)
                break
            except boto.exception.EC2ResponseError:
                if n >= retry_limit - 1:
                    raise
                print "Got an EC2 error, try again to delete ", self.id


class Snapshot(object):
    """
    Class representing a Nova Volume
    """
    def __init__(self, volume=None):
        """
        Create a snapshot from the volume identified.
        """
        if Volume == None:
            raise Exception("No volume passed to Snapshot")

        self.volume = volume

        self.ec2 = EucaConnection()
        self.snapshot = self.ec2.euca.create_snapshot(volume_id=volume.id)
        self.id = self.snapshot.id
        self.volume = self.volume.id
        print "Waiting for snapshot", self.id, "to be created"
        while self.status() == "creating":
            time.sleep(1)

    def status(self):
        """
        Return the status of the Nova volume.
        """
        snaps = self.ec2.euca.get_all_snapshots(snapshot_ids=[self.id])
        return snaps[0].status.split()[0]

    def delete(self):
        """
        Delete the snapshot.
        """
        retry_limit = os.environ.get('NOVA_VOLUME_TEST_RETRY_LIMIT', 3)
        #
        # This call to the euca api fails occasionally, so make a few
        # attempts before giving up.
        #
        print "delete volume %s" % self.id
        for n in xrange(retry_limit):
            try:
                self.ec2.euca.delete_snapshot(self.id)
                break
            except boto.exception.EC2ResponseError:
                if n >= retry_limit - 1:
                    raise
                print "Got an EC2 error, try again to delete ", self.id
