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

from ..utils import get_containers, nested_get

logger = logging.getLogger(__name__)

client = docker.from_env()


def main(args):
    if args.dry_run:
        logger.warning('All manage actions will be done in dry-run mode.')

    if args.manage_action == 'nuke':
        logger.info('Stopping and removing %s containers ...',
                    ('all' if args.all else 'clusterdock'))
        cluster_containers = (get_containers()
                              if args.all else get_containers(clusterdock=True))
        _nuke_containers_and_networks(cluster_containers, args.dry_run, nuke_networks=True)
    if args.manage_action == 'remove':
        logger.info('Stopping and removing containers from cluster(s) %s ...', args.clusters)
        cluster_containers = [cluster_container
                              for cluster_container in get_containers(clusterdock=True)
                              if cluster_container.cluster_name in args.clusters]
        _nuke_containers_and_networks(cluster_containers, args.dry_run, remove_network=args.network)


def _nuke_containers_and_networks(cluster_containers, dry_run,
                                  nuke_networks=False, remove_network=False):
    removed_containers = []
    containers_networks = []
    for cluster_container in cluster_containers:
        container = cluster_container.container
        cluster_name = cluster_container.cluster_name
        if remove_network:
            containers_networks.extend(list(nested_get(container.attrs,
                                                       ['NetworkSettings', 'Networks']).keys()))
        container_hostname = nested_get(container.attrs, ['Config', 'Hostname'])
        logger.debug('Removing container %s (id: %s, cluster: %s) ...',
                     container_hostname, container.short_id, cluster_name)
        if not dry_run:
            _remove_node_from_etc_hosts(container_hostname)
            container.remove(v=True, force=True)
            removed_containers.append(container_hostname)

    if not dry_run and not removed_containers:
        logger.warning("Didn't find any containers to remove. Continuing ...")

    networks_to_remove = []
    if nuke_networks: # `nuke_networks` overrides `remove_network` flag
        networks_to_remove = client.networks.list()
    else:
        for network_name in set(containers_networks):
            networks_to_remove.append(client.networks.get(network_name))

    removed_networks = []
    for network in networks_to_remove:
        try:
            logger.debug('Removing network %s (id: %s) ...', network.name, network.id)
            if not dry_run:
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
        if not dry_run and remove_network:
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
