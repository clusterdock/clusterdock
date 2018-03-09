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

import json
import logging
import subprocess
import tempfile
from itertools import groupby

import docker

from ..config import defaults
from ..utils import nested_get, max_len_list_dict_item

logger = logging.getLogger(__name__)

client = docker.from_env()


def main(args):
    label_key = defaults.get('DEFAULT_DOCKER_LABEL_KEY')
    listed_containers = []
    if client.containers.list():
        for container in client.containers.list(all=True):
            labels = nested_get(container.attrs, ['Config', 'Labels'])
            if label_key in labels:
                label = json.loads(labels[label_key])
                container_hostname = nested_get(container.attrs, ['Config', 'Hostname'])
                ports = nested_get(container.attrs, ['NetworkSettings', 'Ports'])
                network_names = ', '.join(list(nested_get(container.attrs,['NetworkSettings',
                                                                 'Networks']).keys()))
                listed_containers.append({'id': container.short_id, 'hostname': container_hostname,
                                          'ports': (', '.join('{}->{}'.format(v[0]['HostPort'], k)
                                                              for k, v in ports.items())
                                                    if ports else ''),
                                          'image': container.image.tags[0],
                                          'status': container.status, 'name': container.name,
                                          'version': label['version'],
                                          'cluster_name': label['cluster_name'],
                                          'networks': network_names})
    if not listed_containers:
        logger.warning("Didn't find any containers to list")
    else:
        format_str = ('{:<' + str(max_len_list_dict_item(listed_containers, 'id')+6) + '} '
                      '{:<' + str(max_len_list_dict_item(listed_containers, 'hostname')+6) + '} '
                      '{:<' + str(max_len_list_dict_item(listed_containers, 'ports')+6) + '} '
                      '{:<' + str(max_len_list_dict_item(listed_containers, 'status')+6) + '} '
                      '{:<' + str(max_len_list_dict_item(listed_containers, 'name')+6) + '}'
                      '{:<' + str(max_len_list_dict_item(listed_containers, 'version')+6) + '}'
                      '{:<' + str(max_len_list_dict_item(listed_containers, 'image')+6) + '} ')
        sorted_data = sorted(listed_containers, key=lambda x: x['cluster_name'])
        for key, containers in groupby(sorted_data, key=lambda x: x['cluster_name']):
            containers = list(containers)
            print()
            print('For cluster `{}` on network {} '
                  'the node(s) are:'.format(key, containers[0]['networks']))
            print(format_str.format('CONTAINER ID', 'HOST NAME', 'PORTS',
                                    'STATUS', 'CONTAINER NAME', 'VERSION', 'IMAGE'))
            for container in containers:
                print(format_str.format(container['id'], container['hostname'],
                                        container['ports'], container['status'], container['name'],
                                        container['version'], container['image']))
        print()
