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

"""Various utilities to be used by other modules."""

import json
import logging
import operator
import os
import random
import socket
import subprocess
from collections import namedtuple
from functools import reduce
from pkg_resources import get_distribution
from time import sleep, time

import docker

from .config import defaults

logger = logging.getLogger(__name__)

client = docker.from_env()


def nested_get(dict_, keys):
    """Utility function that returns the value of a sequence of nested keys.

    Example:

        >>> details = {'name': {'first': {'english': 'Dima'}}}
        >>> nested_get(details, ['name', 'first', 'english'])
        'Dima'

    Args:
        dict_ (:obj:`dict`): Dictionary to access.
        keys (:obj:`list`): A list of keys to access in a nested manner.

    Returns:
        The value.
    """
    return reduce(operator.getitem, keys, dict_)


# The `#:` constructs at the end of assignments are part of Sphinx's autodoc functionality.
DEFAULT_TIME_BETWEEN_CHECKS = 1  #:
DEFAULT_TIMEOUT = 60  #:
def wait_for_condition(condition, condition_args=None, condition_kwargs=None,
                       time_between_checks=DEFAULT_TIME_BETWEEN_CHECKS, timeout=DEFAULT_TIMEOUT,
                       time_to_success=0, success=None, failure=None):
    """Wait until a condition is satisfied (or timeout).

    Args:
        condition: Callable to evaluate.
        condition_args (optional): A list of args to pass to the
            ``condition``. Default: ``None``
        condition_kwargs (optional): A dictionary of kwargs to pass to the
            ``condition``. Default: ``None``
        time_between_checks (:obj:`int`, optional): Seconds between condition checks.
            Default: :py:const:`DEFAULT_TIME_BETWEEN_CHECKS`
        timeout (:obj:`int`, optional): Seconds to wait before timing out.
            Default: :py:const:`DEFAULT_TIMEOUT`
        time_to_success (:obj:`int`, optional): Seconds for the condition to hold true
            before it is considered satisfied. Default: ``0``
        success (optional): Callable to invoke when ``condition`` succeeds. A ``time``
            variable will be passed as an argument, so can be used. Default: ``None``
        failure (optional): Callable to invoke when timeout occurs. ``timeout`` will
            be passed as an argument. Default: ``None``

    Raises:
        :py:obj:`TimeoutError`
    """
    start_time = time()
    stop_time = start_time + timeout

    success_start_time = None

    while time() < stop_time:
        outcome = condition(*condition_args or [], **condition_kwargs or {})
        if outcome:
            success_start_time = success_start_time or time()
            if time() >= success_start_time + time_to_success:
                if success is not None:
                    success(time='{:.3f}'.format(time() - start_time))
                return
        else:
            success_start_time = None
        sleep(time_between_checks)

    failure(timeout=timeout)


def join_url_parts(*parts):
    """
    Join a URL from a list of parts. See http://stackoverflow.com/questions/24814657 for
    examples of why urllib.parse.urljoin is insufficient for what we want to do.
    """
    return '/'.join([piece.strip('/') for piece in parts])


def version_tuple(version):
    """
    Convert a version string or tuple to a tuple.
    Will return (major, minor, release) kind of format.
    """
    if isinstance(version, str):
        return tuple(int(x) for x in version.split('.'))
    elif isinstance(version, tuple):
        return version


def version_str(version):
    """
    Convert a version tuple or string to a string.
    Will return major.minor.release kind of format.
    """
    if isinstance(version, str):
        return version
    elif isinstance(version, tuple):
        return '.'.join([str(int(x)) for x in version])


def get_clusterdock_label(cluster_name=None):
    """
    Generate a clusterdock meta data label in json format. Meta data such as: clusterdock
    package name, version, location of clusterdock install, etc.

        Args:
            cluster_name (:obj:`str`, optional): Cluster name to attach to meta data label.
                Default: ``None``

        Returns:
            (json): clusterdock meta data label
    """
    label_str = ''
    try:
        package = get_distribution('clusterdock')
        label_info = {'name': package.project_name, 'version': package.version,
                      'location': package.location}
        if cluster_name:
            label_info['cluster_name'] = cluster_name
        label_str = json.dumps(label_info)
    except:
        pass
    return label_str


ADJECTIVES = ['accurate', 'actual', 'angular', 'associative', 'astronomical', 'asymmetrical',
              'available', 'beautiful', 'biggest', 'bimodal', 'biochemical', 'biological',
              'bright', 'celestial', 'closest', 'colorful', 'comparable', 'computational',
              'consistent', 'conspicuous', 'continuous', 'conventional', 'coolest', 'cosmic',
              'cosmological', 'critical', 'crucial', 'cubic', 'deeper', 'different',
              'difficult', 'distant', 'dynamical', 'early', 'easiest', 'efficient',
              'electromagnetic', 'empirical', 'evolutionary', 'faster', 'favorable', 'fewer',
              'fissile', 'fissionable', 'functional', 'galactic', 'gaseous', 'gaussian',
              'gravitational', 'greater', 'gregarious', 'hard', 'heaviest', 'hierarchical',
              'highest', 'historical', 'homogeneous]', 'hot', 'impervious', 'important',
              'intelligent', 'intense', 'intergalactic', 'internal', 'interstellar', 'intrinsic',
              'invisible', 'kinetic', 'largest', 'linear', 'magnetic', 'mechanical',
              'molecular', 'morphological', 'naive', 'nearest', 'nuclear', 'obvious',
              'oldest', 'optical', 'orbital', 'outer', 'outward', 'perceptible',
              'photographic', 'photometric', 'physical', 'planetary', 'precise', 'proper',
              'random', 'reliable', 'richest', 'robust', 'rotational', 'scientific',
              'shortest', 'significant', 'similar', 'skeletal', 'smallest', 'solar',
              'southern', 'spectral', 'spectroscopic', 'spherical', 'strong', 'subsequent',
              'successful', 'sufficient', 'systematic', 'terrestrial', 'thematic', 'tidal',
              'tighter', 'typical', 'uncertain', 'uncollected', 'unformed', 'unlikely',
              'unrelated', 'unresolved', 'unstable', 'unusual',
              'useful', 'violent', 'visible', 'visual', 'weak']


# Astro cluster names
NAMES = ['antlia', 'bullet', 'carolines_rose', 'centaurus', 'chandelier', 'coathanger',
         'coma', 'double', 'el_gordo', 'fornax', 'globular', 'hyades', 'hydra',
         'laniakea_super', 'm22', 'm35', 'mayall2', 'musket_ball', 'ngc752', 'norma',
         'omicron_velorum', 'pandora', 'phoenix', 'pleiades', 'praesepe', 'ptolemy', 'pyxis',
         'reticulum', 'beehive', 'hercules', 'wild_duck', 'virgo']


def generate_cluster_name():
    """
    Generate a random cluster name.
    """
    return '{}_{}'.format(random.choice(ADJECTIVES), random.choice(NAMES))


def print_topology_meta(topology_name, quiet=False):
    """
    Given a toplogy name, relative to current directory, print its meta info.
    """
    try:
        if not quiet:
            git_dir = os.path.join(os.path.realpath(topology_name), '.git')
            out = subprocess.check_output('git --git-dir {} rev-parse --short HEAD'.format(git_dir),
                                          shell=True, stderr=subprocess.STDOUT).strip().decode()
            logger.info('%s has Git hash %s', topology_name, out)
    except:
        pass


def get_containers(clusterdock=False):
    """
    Get Docker containers.

    Args:
        clusterdock (:obj:`bool`, optional): clusterdock containers only. Default: ``False``

    Returns:
        (:obj:`list`): List of containers.
    """
    Container = namedtuple('Container', ['cluster_name', 'container'])
    label_key = defaults['DEFAULT_DOCKER_LABEL_KEY']
    cluster_containers = []
    if client.containers.list():
        for container in client.containers.list(all=True):
            if not clusterdock:
                cluster_containers.append(Container(None, container))
            else:
                labels = nested_get(container.attrs, ['Config', 'Labels'])
                if label_key in labels:
                    label = json.loads(labels[label_key])
                    cluster_containers.append(Container(label['cluster_name'], container))
    return cluster_containers


def max_len_list_dict_item(list_dict, attr):
    """
    Returns max length of a given attribute from a list of dict items.
    """
    length = 0
    for item in list_dict:
        length = length if length > len(item[attr]) else len(item[attr])
    return length


def get_container(hostname):
    """
    Get running Docker container for a given hostname.
    """
    for container in client.containers.list():
        if nested_get(container.attrs, ['Config', 'Hostname']) == hostname:
            return container
