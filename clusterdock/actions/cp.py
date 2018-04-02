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
import io
import tarfile

from ..exceptions import NodeNotFoundError
from ..utils import get_container

logger = logging.getLogger(__name__)


def main(args):
    if args.source == args.destination:
        raise ValueError('Cannot have the same source and destination')

    if ':' in args.source and ':' in args.destination:
        src_container = _find_container(args.source.split(':')[0])
        dest_container = _find_container(args.destination.split(':')[0])
        src_path = args.source.split(':')[1]
        dest_path = args.destination.split(':')[1]

        tarstream = io.BytesIO()
        for chunk in src_container.get_archive(path=src_path)[0]:
            tarstream.write(chunk)
        tarstream.seek(0)
        dest_container.put_archive(path=dest_path, data=tarstream)
    elif ':' in args.source:
        src_container = _find_container(args.source.split(':')[0])
        src_path = args.source.split(':')[1]

        tarstream = io.BytesIO()
        for chunk in src_container.get_archive(path=src_path)[0]:
            tarstream.write(chunk)
        tarstream.seek(0)
        with tarfile.open(fileobj=tarstream) as tarfile_:
            tarfile_.extractall(path=args.destination)
    elif ':' in args.destination:
        dest_container = _find_container(args.destination.split(':')[0])
        dest_path = args.destination.split(':')[1]

        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w') as tarfile_:
            tarfile_.add(args.source, arcname=args.source.split('/')[-1])
        data.seek(0)
        dest_container.put_archive(path=dest_path, data=data)
    else:
        raise ValueError('Source node FQDN or Destination node FQDN required')


def _find_container(node):
    container = get_container(hostname=node)
    if not container:
        raise NodeNotFoundError(node)
    return container
