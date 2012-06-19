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
Tools to ssh to a nova instance
"""

import paramiko
from paramiko.client import SSHClient
from paramiko.rsakey import RSAKey
from paramiko import SSHException
from StringIO import StringIO
import subprocess
import os


def setup_ssh_connection(ip, key, user='root', port=22, timeout=10):
    """
    Construct an ssh connection to the VM instance.
    """
    print "Attempting to setup ssh connection to %s@%s:%d" % (user, ip, port)
    if key is None:
        raise Exception("setup_ssh_connection: You didn't supply a key!")

    try:
        if os.getenv("BOCK_TEST_DEBUG", 0) > 0:
            paramiko.common.logging.basicConfig(level=paramiko.common.DEBUG)
        client = SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(ip, port, user, pkey=key, timeout=timeout)
        print "SSH connection successful"
    except SSHException as e:
        print "Failed to ssh to %s (%s)" % (ip, e)
        raise
    # Check if this is a new ubuntu cloud image that discourages the use
    # of the root account
    cmd = "echo YES"
    stdin, stdout, stderr = client.exec_command(cmd)
    stdout = stdout.readline()
    if stdout != "YES\n":
        print "Test of ssh connection failed"
        print "Got: %s" %  stdout

        if stdout == 'Please login as the user "ubuntu" rather than the user "root".\n':
            print "New style ubuntu image found, using user ubuntu"
            client = SSHClient()
            client.set_missing_host_key_policy(paramiko.WarningPolicy())
            client.connect(ip, port, "ubuntu", pkey=key, timeout=timeout)
            print "SSH connection successful"
            cmd = "echo YES"
            stdin, stdout, stderr = client.exec_command(cmd)
            stdout = stdout.readline()
            if stdout != "YES\n":
                print "Re-test of ssh connection failed"
                print "Got: %s" % stdout
                raise Exception("SSH connection test failed")
            print "SSH connection using user 'ubuntu' successful"
            return client
        else:
            raise Exception("SSH connection test failed")
    return client

def generate_keypair_files(filename, passphrase="", type="rsa"):
    print "Generating new ssh keypair %s" % (filename)
    cmd = ["ssh-keygen", "-f", str(filename), "-t", type, "-N", passphrase]
    subprocess.check_call(cmd)

def load_ssh_key_from_file(filename):
    """
    Load an ssh key from a file into a paramiko RSAKey object
    """
    with open(filename, 'r') as fd:
        key = RSAKey(file_obj=fd)
        return key

def load_ssh_key_from_keypair(kp):
    """
    Load a nova keypair object into a paramiko RSAKey
    """
    keyfileobject = StringIO()
    keyfileobject.write(kp.material)
    keyfileobject.seek(0)
    key = RSAKey(file_obj=keyfileobject)
    return key

