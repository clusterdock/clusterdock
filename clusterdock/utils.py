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

import logging
import operator
import os
import random
import socket
import subprocess
from functools import reduce
from time import sleep, time

logger = logging.getLogger(__name__)


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


def max_len_list_dict_item(list_dict, attr):
    """
    Returns max length of a given attribute from a list of dict items.
    """
    length = 0
    for item in list_dict:
        length = length if length > len(item[attr]) else len(item[attr])
    return length


ADJECTIVES = ['bright', 'new', 'pointed', 'red', 'single', 'brightest', 'big', 'white', 'fixed',
              'yellow', 'double', 'nearest', 'central', 'lucky', 'famous', 'polar',
              'particular', 'distant', 'former', 'brilliant', 'pole', 'variable', 'massive',
              'blue', 'day', 'beautiful', 'evil', 'faint', 'popular', 'female',
              'biggest', 'golden', 'giant', 'blazing', 'favorite', 'hot', 'lone',
              'morning', 'fallen', 'north', 'tiny', 'male', 'brittle', 'dark',
              'solitary', 'top', 'unlucky', 'type', 'typical', 'huge', 'porn',
              'northern', 'farthest', 'rayed', 'pale', 'nearby', 'green', 'brighter',
              'musical', 'time', 'dead', 'silent', 'all', 'luminous', 'bunch',
              'clump', 'flock', 'agglomeration', 'bundle', 'constellate', 'swad', 'huddle',
              'forgather', 'agglomerate', 'pleiades', 'tuft', 'collective', 'mass', 'component',
              'fragmentation', 'nucleus', 'heap', 'aggregation', 'clustering', 'tussock', 'knot',
              'foregather', 'clusters', 'mob', 'supergroup', 'collection', 'multitude', 'bevy',
              'amass', 'sabha', 'regroup', 'congregate', 'globular', 'uncollected', 'batch',
              'larger', 'groud', 'components', 'compound', 'gatherer', 'structures', 'semigroup',
              'cortege', 'convocation', 'concourse', 'gang', 'fragments', 'shells', 'plant',
              'cells', 'embedded', 'acyl', 'measuring', 'detected', 'markers', 'monoid',
              'distinct', 'complexes', 'localized', 'scattered', 'congregation', 'craters',
              'flattened', 'explosive', 'quintet']


# Astro cluster names
NAMES = ['Antlia', 'Bullet', 'CarolinesRose', 'Centaurus', 'Chandelier', 'Coathanger',
         'Coma', 'Double', 'ElGordo', 'Fornax', 'Globular', 'Hyades', 'Hydra',
         'LaniakeaSuper', 'M22', 'M35', 'MayallII', 'MusketBall', 'NGC752', 'Norma',
         'OmicronVelorum', 'Pandora', 'Phoenix', 'Pleiades', 'Praesepe', 'Ptolemy', 'Pyxis',
         'Reticulum', 'Beehive', 'Hercules', 'WildDuck', 'Virgo']


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
            topology_dir = os.path.realpath(topology_name)
            logger.info('%s is running out of %s', topology_name, topology_dir)
            git_dir = os.path.join(topology_dir, '.git')

            cmd = ['git', '--git-dir', git_dir, 'ls-remote', '--get-url']
            child = subprocess.Popen(cmd, stdout = subprocess.PIPE)
            out = child.communicate()[0]
            if child.returncode == 0:
                out = out.strip().decode('ascii')
                logger.info('%s is using %s remote URL', topology_name, out)

            cmd = ['git', '--git-dir', git_dir, 'rev-parse', '--short', 'HEAD']
            child = subprocess.Popen(cmd, stdout = subprocess.PIPE)
            out = child.communicate()[0]
            if child.returncode == 0:
                out = out.strip().decode('ascii')
                logger.info('%s is using %s git hash', topology_name, out)
    except:
        pass
