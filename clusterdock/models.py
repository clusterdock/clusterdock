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

"""This module contains the main abstractions used by clusterdock topologies
to bring up clusters.
"""

import datetime
import logging

import docker
import requests

from .exceptions import DuplicateHostnamesError
from .utils import nested_get

logger = logging.getLogger(__name__)

client = docker.from_env()

DEFAULT_NETWORK_TYPE = 'bridge'


class Cluster:
    """The central abstraction for interacting with Docker container clusters.
    No Docker behavior is actually invoked until the start method is called.

    Args:
        *nodes: One or more :py:obj:`clusterdock.models.Node` instances.
    """

    def __init__(self, *nodes):
        self.nodes = nodes
        self.node_groups = {}

        for node in self.nodes:
            if node.group not in self.node_groups:
                logger.debug('Creating NodeGroup %s ...',
                             node.group)
                self.node_groups[node.group] = NodeGroup(node.group, node)
            else:
                self.node_groups[node.group].nodes.append(node)
            # Put this outside the if-else because, whether a new NodeGroup is created
            # or not, the node will be added to it.
            logger.debug('Adding node (%s) to NodeGroup %s ...',
                         node.hostname,
                         node.group)

    def start(self, network, pull_images=False, update_etc_hosts=True):
        """Start the cluster.

        Args:
            network (:obj:`str`): Name of the Docker network to use for the cluster.
            pull_images (:obj:`bool`, optional): Pull every Docker image needed by every
                :py:obj:`clusterdock.models.Node` instance, even if it exists locally.
                Default: ``False``
            update_etc_hosts (:obj:`bool`): Update the /etc/hosts file on the host with the hostname
                and IP address of the container. Default: ``True``
        """
        start_cluster_start_time = datetime.datetime.now()
        logger.info('Starting cluster on network (%s) ...', network)
        the_network = self._setup_network(name=network)

        if len(the_network.containers) != 0:
            # The network alias for a container is deeply nested in the container attributes.
            # Store the hierarchy so we can use the nested_get utility from clusterdock.utils.
            container_network_alias = ['NetworkSettings', 'Networks', network, 'Aliases', 0]
            containers_attached_to_network = [nested_get(container.attrs,
                                                         container_network_alias)
                                              for container in the_network.containers]
            logger.debug('Network (%s) currently has the followed containers attached: \n%s',
                         network,
                         '\n'.join('- {}'.format(container)
                                   for container in containers_attached_to_network))

            duplicate_hostnames = set(containers_attached_to_network) & set(node.hostname
                                                                            for node in self.nodes)
            if duplicate_hostnames:
                raise DuplicateHostnamesError(duplicates=duplicate_hostnames,
                                              network=network)

        for node in self:
            node.start(network)

        start_cluster_duration = datetime.datetime.now() - start_cluster_start_time
        logger.info('Cluster started successfully (total time: %s).',
                    (datetime.datetime.min
                         + start_cluster_duration).time().isoformat(timespec='milliseconds'))

    def execute(self, command, **kwargs):
        """Execute a command on every :py:class:`clusterdock.models.Node` within the
            :py:class:`clusterdock.models.Cluster`.

        Args:
            command (:obj:`str`): Command to execute.
            **kwargs: Additional keyword arguments to pass to
                :py:meth:`clusterdock.models.Node.execute`.
        """
        for node in self.nodes:
            node.execute(command, **kwargs)

    def __iter__(self):
        for node in self.nodes:
            yield node

    def _setup_network(self, name):
        try:
            network = client.networks.create(name=name,
                                             driver=DEFAULT_NETWORK_TYPE,
                                             check_duplicate=True)
            logger.debug('Successfully created network (%s).', name)
        except docker.errors.APIError as api_error:
            if (api_error.status_code == requests.codes.server_error and
                    api_error.explanation == 'network with name {} already exists'.format(name)):
                logger.warning('Network (%s) already exists. Continuing without creating ...',
                               name)
                network = client.networks.get(name)
        return network


class NodeGroup:
    """Abstraction representing a collection of Nodes that it could be useful to interact with
    enmasse. For example, a typical HDFS cluster could be seen as consisting of a 1 node group
    consisting of hosts with NameNodes and an n-1 node group of hosts with DataNodes.

    Args:
        name (:obj:`str`): The name by which to refer to the group.
        *nodes: One or more :py:class:`clusterdock.models.Node` instances.
    """
    def __init__(self, name, *nodes):
        self.name = name

        # We want the list of nodes to be mutable, so the tuple we get from *nodes
        # needs to be cast.
        self.nodes = list(nodes)

    def __iter__(self):
        for node in self.nodes:
            yield node

    def execute(self, command, **kwargs):
        """Execute a command on every :py:class:`clusterdock.models.Node` within the
            :py:class:`clusterdock.models.NodeGroup`.

        Args:
            command (:obj:`str`): Command to execute.
            **kwargs: Additional keyword arguments to pass to
                :py:meth:`clusterdock.models.Node.execute`.
        """
        for node in self.nodes:
            node.execute(command, **kwargs)


class Node:
    """Class representing a single cluster host.

    Args:
        hostname (:obj:`str`): Hostname of the node.
        group (:obj:`str`): :py:obj:`clusterdock.models.NodeGroup` to which the node should belong.
        image (:obj:`str`): Docker image with which to start the container.
        ports (:obj:`list`, optional): A list of container ports to expose to the host.
            Default: ``None``
        volumes (:obj:`dict`, optional): A dictionary (key: absolute path on host; value: absolute
            path in container) of volumes to create. Default: ``None``
        volumes_from (:obj:`list`, optional): A list of images whose volumes should be used
            when starting the node. Default: ``None``
        **container_configs: Additional parameters to pass to
            :py:meth:`docker.client.containers.run`.
    """
    DEFAULT_CONTAINER_CONFIGS = {
        # Add all capabilities to make containers host-like.
        'cap_add': ['ALL'],
        # All nodes run in detached mode.
        'detach': True,
        # Run without a seccomp profile.
        'security_opt': ['seccomp=unconfined'],
        # Expose all container ports to the host.
        'publish_all_ports': True,
        # Ensure that a volume mount for /etc/localtime always exists.
        'volumes': {'/etc/localtime': {'bind': '/etc/localtime'}},
    }

    def __init__(self, hostname, group, image,
                 ports=None, volumes=None, volumes_from=None, **container_configs):
        self.hostname = hostname
        self.group = group

        self.container_configs = self._prepare_container_configs(**dict(image=image,
                                                                        ports=ports or [],
                                                                        volumes=volumes or {},
                                                                        **container_configs))
        self.volumes_from = volumes_from

    def start(self, network):
        """Start the node.

        Args:
            network (:obj:`str`): Docker network to which to attach the container.
        """
        self.container_configs.update(dict(hostname='{}.{}'.format(self.hostname, network)))

        if self.volumes_from:
            self.container_configs['volumes_from'] = [client.containers.create(image=image).id
                                                      for image in self.volumes_from]

        logger.debug('Container configs: %s.',
                     '; '.join('{}="{}"'.format(k, v) for k, v in self.container_configs.items()))
        logger.info('Starting node %s.%s ...',
                    self.hostname,
                    network)
        self.container = client.containers.run(**self.container_configs)
        client.networks.get(network).connect(container=self.container,
                                             aliases=[self.hostname])

    def execute(self, command, user='root', quiet=False):
        """Execute a command on the node.

        Args:
            command (:obj:`str`): Command to execute.
            user (:obj:`str`, optional): User with which to execute the command. Default: ``root``
            quiet (:obj:`bool`, optional): Run the command without showing any stdout. Default:
                ``False``
        """
        logger.debug('Executing command (%s).', command)
        for response_chunk in self.container.exec_run(command,
                                                      detach=quiet,
                                                      stream=True,
                                                      user=user):
            print(response_chunk.decode())

    def _prepare_container_configs(self, **container_configs):
        # Build up the container config dictionary which we used to populate kwargs
        # for docker.client.containers.run.
        configs = dict(Node.DEFAULT_CONTAINER_CONFIGS)
        logger.debug('Container configs dictionary contains default values (%s).',
                     ', '.join('{}={}'.format(key, value)
                               for key, value in configs.items()))

        configs['image'] = container_configs['image']
        logger.debug('Added image (%s) to container config.', configs['image'])

        # docker-py expects port bindings as a dictionary with container ports as keys and
        # host ports as values (a host port of None tells it to select a random port).
        if container_configs['ports']:
            configs['ports'] = dict.fromkeys(container_configs['ports'], None)

        volumes = {host_path: {'bind': container_path}
                   for host_path, container_path in container_configs['volumes'].items()}
        if volumes:
            configs['volumes'].update(volumes)
            logger.debug('Added volumes (%s) to container config.',
                         ', '.join('{}=>{}'.format(key, value)
                                   for key, value in volumes.items()))

        return configs
