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

from setuptools import setup, find_packages

setup(name="nova_volume_testing",
      description="Nova Volume system testing",
      author="Duncan Thomas",
      author_email="duncan.thomas@hp.com",
      platforms="Linux",
      packages=['nova_volume_testing',
                'nova_volume_testing.volume_end_to_end',
                'nova_volume_testing.util'],
      scripts=['bin/nova-volume-test']
)

