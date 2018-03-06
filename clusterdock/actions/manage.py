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

import docker

from ..config import defaults
from ..utils import nested_get

logger = logging.getLogger(__name__)

client = docker.from_env()


def main(args):
    if args.dry_run:
        logger.warning('All manage actions will be done in dry-run mode.')

    label_key = defaults.get('DEFAULT_DOCKER_LABEL_KEY')
    if args.manage_action == 'nuke':
        removed_containers = []
        containers_networks = []
        if client.containers.list():
            logger.info('Stopping and removing '
                        '{} ...'.format('cluster {} containers'.format(args.cluster_name)
                                        if args.cluster_name else 'all containers'))
            for container in client.containers.list(all=True):
                labels = nested_get(container.attrs, ['Config', 'Labels'])
                if label_key in labels:
                    label = json.loads(labels[label_key])
                    if (not args.cluster_name or args.cluster_name == label['cluster_name']):
                        container_hostname = nested_get(container.attrs, ['Config', 'Hostname'])
                        containers_networks.extend(
                            list(nested_get(container.attrs,
                                            ['NetworkSettings', 'Networks']).keys()))
                        logger.debug('Removing container %s (id: %s, cluster: %s) ...',
                                     container_hostname, container.short_id, label['cluster_name'])
                        if not args.dry_run:
                            _remove_node_from_etc_hosts(container_hostname)
                            container.remove(v=True, force=True)
                            removed_containers.append(container_hostname)
        if not args.dry_run and not removed_containers:
            logger.warning("Didn't find any containers to remove. Continuing ...")

        # Since we don't know whether any networks were removed until after we loop through them
        # with our try-except block, keep track of them as we go and only display logging info
        # after the fact.
        removed_networks = []
        for network_name in set(containers_networks):
            network = client.networks.get(network_name)
            try:
                labels = nested_get(network.attrs, ['Labels'])
                if label_key in labels:
                    logger.debug('Removing network %s (id: %s) ...', network.name, network.id)
                    if not args.dry_run:
                        network.remove()
                        removed_networks.append(network.name)
            except docker.errors.APIError as api_error:
                if ('is a pre-defined network and cannot be removed' in api_error.explanation
                    or 'has active endpoints' in api_error.explanation):
                    pass
                else:
                    raise api_error
        if removed_networks:
            logger.info('Removed user-defined networks ...')
            for network in removed_networks:
                logger.debug('Removed network %s ...', network)
        else:
            if not args.dry_run:
                logger.warning("Cannot remove network. Didn't find any user-defined networks or "
                               'active containers on the network. Continuing ...')


def _remove_node_from_etc_hosts(fqdn):
        """Remove node information to the Docker hosts' /etc/hosts file, exploiting Docker's
        permissions to do so without needing an explicit sudo.
        """
        image = 'alpine:latest'
        command = ['/bin/sh',
                   '-c',
                   # We have to use echo to write to the file instead of sed -i
                   # because of how Docker volume mounts deal with inodes.
                   'echo "$(sed "/.* {}  # clusterdock/d" /etc/hosts)" > /etc/hosts'.format(fqdn)]
        volumes = {'/etc/hosts': {'bind': '/etc/hosts', 'mode': 'rw'}}

        logger.debug('Removing any instances of %s from /etc/hosts ...', fqdn)
        client.containers.run(image=image,
                              command=command,
                              volumes=volumes,
                              remove=True)
