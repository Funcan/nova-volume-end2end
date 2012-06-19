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
Script to test basic volume creation, mounting and deletion.
"""
from nova_volume_testing.util.novaexerciser import Volume, Instance

if __name__ == "__main__":
    print "001 basic volume create attach - Create a volume, attach it to an "\
          "instance, write to it, dettach it and attach it to a different"\
          "instance, check the data"
    instance1 = Instance()
    instance2 = Instance()
    volume = Volume(size=1)

    assert volume.attached() == False

    volume.attach(instance1)
    assert volume.attached() == True
    assert volume.attached(instance1) == True

    volume.write_test_pattern()
    assert volume.check_test_pattern() == True
    assert volume.check_test_pattern(key=16) == False

    volume.detach()
    assert volume.attached() == False

    volume.attach(instance2)
    assert volume.attached(instance2) == True
    assert volume.check_test_pattern() == True
    volume.write_test_pattern(key=16)
    assert volume.check_test_pattern(key=16) == True

    volume.detach()
    assert volume.attached() == False

    volume.delete()
    instance1.delete()
    instance2.delete()
