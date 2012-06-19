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
Script to test basic snapshot creation mounting and deletion.
"""
from nova_volume_testing.util.novaexerciser import Volume, Instance, Snapshot

if __name__ == "__main__":
    print "002 basic snapshot - Create a volume, write to it, snapshot it, "\
          "create a volume from the snapshot, change original, check "\
          "snapshot, change snapshot, check original"
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

    snapvol.write_test_pattern(key=2, percentage=10)
    assert snapvol.check_test_pattern(key=2, percentage=10) == True

    volume.attach(instance)

    assert volume.check_test_pattern(key=1) == True

    volume.write_test_pattern(key=3, percentage=10)
    assert volume.check_test_pattern(key=3, percentage=10) == True
    assert snapvol.check_test_pattern(key=2, percentage=10) == True

    snapvol2 = Volume(snapshot=snapshot)
    snapvol2.attach(instance)

    assert snapvol2.check_test_pattern(key=1) == True
    assert snapvol.check_test_pattern(key=2, percentage=10) == True
    assert volume.check_test_pattern(key=3, percentage=10) == True

    volume.detach()
    snapvol.detach()
    snapvol2.detach()

    snapvol.delete()
    snapvol2.delete()
    snapshot.delete()
    volume.delete()
    instance.delete()
