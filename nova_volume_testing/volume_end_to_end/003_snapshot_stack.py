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
Script to test creation of a stack of volumes 2 voumes deep.
"""
from nova_volume_testing.util.novaexerciser import Volume, Instance, Snapshot

if __name__ == "__main__":
    print "003 snapshot stack - create snapshots of volumes that were created "\
          "from snapshots, check all volumes can be changed without "\
          "corrupting other volumes"
    instance = Instance()
    volume = Volume(size=1)
    assert volume.attached() == False

    volume.attach(instance)
    assert volume.attached() == True
    assert volume.attached(instance) == True
    volume.write_test_pattern(key=1)
    assert volume.check_test_pattern(key=1) == True
    volume.detach()
    assert volume.attached() == False

    snapshot = Snapshot(volume)
    snapvol = Volume(snapshot=snapshot)
    snapvol.attach(instance)
    assert snapvol.check_test_pattern(key=1) == True
    snapvol.write_test_pattern(key=2)
    assert snapvol.check_test_pattern(key=2) == True

    volume.attach(instance)
    assert volume.check_test_pattern(key=1) == True
    volume.write_test_pattern(key=3)
    assert volume.check_test_pattern(key=3) == True
    assert snapvol.check_test_pattern(key=2) == True
    snapvol.detach()
    assert snapvol.attached() == False

    snapshot2 = Snapshot(snapvol)
    snapvol2 = Volume(snapshot=snapshot2)
    snapvol2.attach(instance)
    assert snapvol2.check_test_pattern(key=2) == True
    snapvol2.write_test_pattern(key=4)
    assert snapvol2.check_test_pattern(key=4) == True
    snapvol.attach(instance)
    assert snapvol.attached() == True
    assert snapvol.check_test_pattern(key=2) == True
    assert volume.check_test_pattern(key=3) == True

    volume.detach()
    assert volume.attached() == False
    snapvol.detach()
    assert snapvol.attached() == False
    snapvol2.detach()
    assert snapvol2.attached() == False

    snapvol2.delete()
    snapshot2.delete()
    snapvol.delete()
    snapshot.delete()
    volume.delete()
    instance.delete()
