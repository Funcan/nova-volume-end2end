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
import os
from nova_volume_testing.util.novaexerciser import Volume, Instance

if __name__ == "__main__":
    print "004 Test pre-existing volumes - Make sure volumes from before the "\
          "upgrade still work"
    if 'BOCK_TEST_VOLUMES' in os.environ:
        #
        # Make a list of volume id's, one from each line in the volumes file.
        # Then make a list of volume objects from each volume id.
        vol_list = [l.strip() for l in file(os.environ['BOCK_TEST_VOLUMES'])]
        volumes = [Volume(volume_id=v_id) for v_id in vol_list]

        if len(volumes) > 0:
            print 'Testing %s volumes' % len(volumes)

            instance = Instance()
            for volume in volumes:
                assert volume.attached() == False
                volume.attach(instance)
                assert volume.attached(instance) == True
                assert volume.check_mount_device() == True
                volume.detach()
                assert volume.attached() == False
            instance.delete()
        else:
            print "There are no volumes listed in %s" % \
                                            os.environ['BOCK_TEST_VOLUMES']
    else:
        print 'The environment variable BOCK_TEST_VOLUMES is not set'
