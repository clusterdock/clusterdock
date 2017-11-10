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

import copy
import datetime
import io
import logging
import tarfile
import time
from collections import OrderedDict, namedtuple

import docker
import requests

from .exceptions import DuplicateHostnamesError
from .utils import nested_get, wait_for_condition

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
        logger.info('Starting cluster on network (%s) ...', network)
        self.network = network
        the_network = self._setup_network(name=self.network)

        if len(the_network.containers) != 0:
            containers_attached_to_network = [nested_get(container.attrs,
                                                         ['NetworkSettings',
                                                          'Networks',
                                                          self.network,
                                                          'Aliases',
                                                          0])
                                              for container in the_network.containers]
            logger.debug('Network (%s) currently has the followed containers attached: \n%s',
                         self.network,
                         '\n'.join('- {}'.format(container)
                                   for container in containers_attached_to_network))

            duplicate_hostnames = set(containers_attached_to_network) & set(node.hostname
                                                                            for node in self.nodes)
            if duplicate_hostnames:
                raise DuplicateHostnamesError(duplicates=duplicate_hostnames,
                                              network=self.network)

        for node in self:
            node.start(self.network)

    def execute(self, command, **kwargs):
        """Execute a command on every :py:class:`clusterdock.models.Node` within the
            :py:class:`clusterdock.models.Cluster`.

        Args:
            command (:obj:`str`): Command to execute.
            **kwargs: Additional keyword arguments to pass to
                :py:meth:`clusterdock.models.Node.execute`.

        Returns:
            A :py:class:`collections.OrderedDict` of :obj:`str` instances (the FQDN of the node)
                mapping to the :py:class:`collections.namedtuple` instances returned by
                :py:meth:`clusterdock.models.Node.execute`.
        """
        return OrderedDict((node.fqdn, node.execute(command, **kwargs)) for node in self.nodes)

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
            if api_error.explanation == 'network with name {} already exists'.format(name):
                logger.warning('Network (%s) already exists. Continuing without creating ...',
                               name)
                network = client.networks.get(name)
            else:
                raise
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

        Returns:
            A :py:class:`collections.OrderedDict` of :obj:`str` instances (the FQDN of the node)
                mapping to the :py:class:`collections.namedtuple` instances returned by
                :py:meth:`clusterdock.models.Node.execute`.
        """
        return OrderedDict((node.fqdn, node.execute(command, **kwargs)) for node in self.nodes)


class Node:
    """Class representing a single cluster host.

    Args:
        hostname (:obj:`str`): Hostname of the node.
        group (:obj:`str`): :py:obj:`clusterdock.models.NodeGroup` to which the node should belong.
        image (:obj:`str`): Docker image with which to start the container.
        ports (:obj:`list`, optional): A list of container ports to expose to the host. Elements of
            the list could be integers (in which case a random port on the host will be chosen by
            the Docker daemon) or dictionaries (with the key being the host port and the value being
            the container port). Default: ``None``
        volumes (:obj:`list`, optional): A list of volumes to create for the node. Elements of the
            list could be dictionaries of bind volumes (i.e. key: the absolute path on the host,
            value: the absolute path in the container) or strings representing the names of
            Docker images from which to get volumes. As an example,
            ``[{'/var/www': '/var/www'}, 'my_super_secret_image']`` would create a bind mount of
            ``/var/www`` on the host and use any volumes from ``my_super_secret_image``.
            Default: ``None``
        devices (:obj:`list`, optional): Devices on the host to expose to the node. Default:
            ``None``
        **create_container_kwargs: Any other keyword arguments to pass directly to
            :py:meth:`docker.api.container.create_container`.
    """
    DEFAULT_CREATE_HOST_CONFIG_KWARGS = {
        # Add all capabilities to make containers host-like.
        'cap_add': ['ALL'],
        # Run without a seccomp profile.
        'security_opt': ['seccomp=unconfined'],
        # Mount in /etc/localtime to have container time match the host's.
        'binds': {'/etc/localtime': {'bind': '/etc/localtime', 'mode': 'rw'}},
    }

    DEFAULT_CREATE_CONTAINER_KWARGS = {
        # All nodes run in detached mode.
        'detach': True,
        # Mount in /etc/localtime to have container time match the host's.
        'volumes': ['/etc/localtime']
    }

    def __init__(self, hostname, group, image, ports=None, volumes=None, devices=None,
                 **create_container_kwargs):
        self.hostname = hostname
        self.group = group
        self.image = image

        self.ports = ports or []
        self.volumes = volumes or []
        self.devices = devices or []
        self.create_container_kwargs = create_container_kwargs

        self.execute_shell = '/bin/sh'

    def start(self, network):
        """Start the node.

        Args:
            network (:obj:`str`): Docker network to which to attach the container.
        """
        self.fqdn = '{}.{}'.format(self.hostname, network)

        # Instantiate dictionaries for kwargs we'll pass when creating host configs
        # and the node's container itself.
        create_host_config_kwargs = copy.deepcopy(Node.DEFAULT_CREATE_HOST_CONFIG_KWARGS)
        create_container_kwargs = copy.deepcopy(dict(Node.DEFAULT_CREATE_CONTAINER_KWARGS,
                                                **self.create_container_kwargs))

        if self.volumes:
            # Instantiate empty lists to which we'll append elements as we traverse through
            # volumes. These populated lists will then get passed to either
            # :py:meth:`docker.api.client.APIClient.create_host_config` or
            # :py:meth:`docker.api.client.create_container`.
            binds = {}
            volumes = []

            volumes_from = []

            for volume in self.volumes:
                if isinstance(volume, dict):
                    # Dictionaries in the volumes list are bind volumes.
                    for host_directory, container_directory in volume.items():
                        logger.debug('Adding volume (%s) to container config ...',
                                     '{} => {}'.format(host_directory, container_directory))
                        binds[host_directory] = dict(bind=container_directory, mode='rw')
                        volumes.append(container_directory)
                elif isinstance(volume, str):
                    # Strings in the volume list are `volumes_from` images.
                    try:
                        container = client.containers.create(volume)
                    except docker.errors.ImageNotFound:
                        logger.info('Could not find %s locally. Attempting to pull ...', volume)
                        client.images.pull(volume)
                        container = client.containers.create(volume)
                    volumes_from.append(container.id)
                else:
                    element_type = type(element).__name__
                    raise TypeError('Saw volume of type {} (must be dict or str).'.format(element_type))

            if volumes_from:
                create_host_config_kwargs['volumes_from'] = volumes_from

            if volumes:
                create_host_config_kwargs['binds'].update(binds)
                create_container_kwargs['volumes'] += volumes

        ports = []
        port_bindings = {}
        for port in self.ports:
            if isinstance(port, dict):
                for host_port, container_port in port.items():
                    logger.debug('Adding binding from host port %s to container port %s ...',
                                 host_port, container_port)
                    ports.append(container_port)
                    port_bindings[container_port] = host_port
            elif isinstance(port, int):
                ports.append(port)
                port_bindings[port] = None
            else:
                element_type = type(element).__name__
                raise TypeError('Saw port of type {} (must be dict or int).'.format(element_type))

        if ports:
            create_container_kwargs['ports'] = ports
        if port_bindings:
            create_host_config_kwargs['port_bindings'] = port_bindings

        if self.devices:
            create_host_config_kwargs['devices'] = self.devices

        host_config = client.api.create_host_config(**create_host_config_kwargs)

        # Pass networking config to container at creation time to avoid issues with
        # DNS resolution.
        networking_config = client.api.create_networking_config({
            network: client.api.create_endpoint_config(aliases=[self.hostname])
        })

        logger.info('Starting node %s ...', self.fqdn)
        # Since we need to use the low-level API to handle networking properly, we need to get
        # a container instance from the ID
        try:
            container_id = client.api.create_container(image=self.image,
                                                       hostname=self.fqdn,
                                                       host_config=host_config,
                                                       networking_config=networking_config,
                                                       **create_container_kwargs)['Id']
        except docker.errors.ImageNotFound:
            logger.info('Could not find %s locally. Attempting to pull ...', self.image)
            client.images.pull(self.image)
            container_id = client.api.create_container(image=self.image,
                                                       hostname=self.fqdn,
                                                       host_config=host_config,
                                                       networking_config=networking_config,
                                                       **create_container_kwargs)['Id']
        client.api.start(container=container_id)

        # When the Container instance is created, the corresponding Docker container may not
        # be in a RUNNING state. Wait until it is (or until timeout takes place).
        self.container = client.containers.get(container_id=container_id)

        logger.debug('Connecting container (%s) to network (%s) ...', self.container.short_id, network)

        # Wait for container to be in running state before moving on.
        def condition(container):
            container.reload()
            outcome = nested_get(container.attrs, ['State', 'Running'])
            logger.debug('Container running state evaluated to %s.', outcome)
            return outcome
        def success(time):
            logger.debug('Container reached running state after %s seconds.', time)
        def failure(timeout):
            logger.debug('Timed out after %s seconds waiting for container to reach running state.',
                         timeout)
        timeout_in_secs = 30
        wait_for_condition(condition=condition, condition_args=[self.container],
                           timeout=30, success=success, failure=failure)

        logger.debug('Reloading attributes for container (%s) ...', self.container.short_id)
        self.container.reload()

        self.ip_address = nested_get(self.container.attrs,
                                     ['NetworkSettings', 'Networks', network, 'IPAddress'])

        self.host_ports = {int(container_port.split('/')[0]): int(host_ports[0]['HostPort'])
                           for container_port, host_ports in nested_get(self.container.attrs,
                                                                        ['NetworkSettings',
                                                                         'Ports']).items()}
        if self.host_ports:
            logger.debug('Created host port mapping (%s) for node (%s).',
                         '; '.join('{} => {}'.format(host_port, container_port)
                                   for host_port, container_port in self.host_ports.items()),
                         self.hostname)

    def execute(self, command, user='root', quiet=False, detach=False):
        """Execute a command on the node.

        Args:
            command (:obj:`str`): Command to execute.
            user (:obj:`str`, optional): User with which to execute the command. Default: ``root``
            quiet (:obj:`bool`, optional): Run the command without showing any output. Default:
                ``False``
            detach (:obj:`bool`, optional): Run the command in detached mode. Default:
                ``False``

        Returns:
            A :py:class:`collections.namedtuple` instance with `exit_code` and `output` attributes.
        """
        logger.debug('Executing command (%s) on node (%s) ...', command, self.fqdn)
        exec_command = [self.execute_shell, '-c', command]
        logger.debug('Running docker exec with command (%s) ...', exec_command)
        exec_id = client.api.exec_create(self.container.id, exec_command, user=user)['Id']

        output = []
        for response_chunk in client.api.exec_start(exec_id, stream=True, detach=detach):
            output_chunk = response_chunk.decode()
            output.append(output_chunk)
            if not quiet:
                print(output_chunk)
        exit_code = client.api.exec_inspect(exec_id).get('ExitCode')
        return namedtuple('ExecuteSession', ['exit_code', 'output'])(exit_code=exit_code,
                                                                     output=''.join(output))

    def get_file(self, path):
        """Get file from the node.

        Args:
            path (:obj:`str`): Absolute path to file.

        Returns:
            A :obj:`str` containing the contents of the file.
        """
        tarstream = io.BytesIO(self.container.get_archive(path=path)[0].read())
        with tarfile.open(fileobj=tarstream) as tarfile_:
            for tarinfo in tarfile_.getmembers():
                return tarfile_.extractfile(tarinfo).read().decode()

    def put_file(self, path, contents):
        """Put file on the node.

        Args:
            path (:obj:`str`): Absolute path to file.
            contents (:obj:`str`): The contents of the file.
        """
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w') as tarfile_:
            encoded_file = contents.encode()
            tarinfo = tarfile.TarInfo(path)

            # We set the modification time to now because some parts of SDC (e.g. logging) rely upon
            # timestamps to determine whether to read config files.
            tarinfo.mtime = time.time()
            tarinfo.size = len(encoded_file)
            tarfile_.addfile(tarinfo, io.BytesIO(encoded_file))
        data.seek(0)

        self.container.put_archive(path='/', data=data)
