# -*- coding: utf-8 -*-
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os
import subprocess
import tempfile

import docker

from ..exceptions import NodeNotFoundError
from ..utils import nested_get

logger = logging.getLogger(__name__)

client = docker.from_env()


def main(args):
    if args.source == args.destination:
        raise ValueError('Cannot have source and destination the same')

    options = '{} {}'.format('-a' if args.archive else '',
                             '-L' if args.follow_link else '')
    if ':' in args.source and ':' in args.destination:
        src_container = _find_container(args.source.split(':')[0])
        dest_container = _find_container(args.destination.split(':')[0])

        with tempfile.TemporaryDirectory() as tmp_dir:
            src_path = '{}:{}'.format(src_container.id, args.source.split(':')[1])
            dest_path = '{}:{}'.format(dest_container.id, args.destination.split(':')[1])
            subprocess.Popen('docker cp {} {} {}'.format(options, src_path, tmp_dir),
                             shell=True).communicate()
            subprocess.Popen('docker cp {} {} {}'.format(options, os.path.join(tmp_dir, '*'),
                                                         dest_path),
                             shell=True).communicate()
    elif ':' in args.source:
        src_container = _find_container(args.source.split(':')[0])
        src_path = '{}:{}'.format(src_container.id, args.source.split(':')[1])
        subprocess.Popen('docker cp {} {} {}'.format(options, src_path, args.destination),
                         shell=True).communicate()
    elif ':' in args.destination:
        dest_container = _find_container(args.destination.split(':')[0])
        dest_path = '{}:{}'.format(dest_container.id, args.destination.split(':')[1])
        subprocess.Popen('docker cp {} {} {}'.format(options, args.source, dest_path),
                         shell=True).communicate()
    else:
        raise ValueError('Source node FQDN or Destination node FQDN required')


def _find_container(node):
    for container in client.containers.list():
        if nested_get(container.attrs, ['Config', 'Hostname']) == node:
            break
    else:
        raise NodeNotFoundError(node)
    return container
