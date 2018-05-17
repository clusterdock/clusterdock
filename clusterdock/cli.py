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

import argparse
import datetime
import importlib
import logging
import os
import sys
from dateutil.relativedelta import relativedelta

import yaml

import clusterdock.models as models
from .config import CLUSTERDOCK_CONFIG_DIRECTORY, defaults

FORMATTER_CLASS = argparse.ArgumentDefaultsHelpFormatter

# Note that while we use a `logging.Logger` instance throughout (to make tracing easier),
# we set the logging level on the root logger based on whether -v/--verbose is passed.
logger = logging.getLogger(__name__)


def main():
    # To prevent a -h argument from halting parsing prematurely, we disable
    # help in the parser, but then add it manually after parse_known_args is run.
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-v', '--verbose', action='store_true', help='Be noisier')

    # Parse known args the first time to set the logger level early on. Note that
    # argparse.ArgumentParser.parse_known_args returns a tuple where the first element is a
    # Namespace.
    args, unknown_args = parser.parse_known_args()
    logging.getLogger().setLevel(logging.DEBUG if args.verbose else logging.INFO)
    logger.debug('Parsed known args (%s) and found unknown args (%s).',
                 '; '.join('{}="{}"'.format(k, v) for k, v in vars(args).items()),
                 '; '.join(unknown_args))

    # Since some actions (e.g. start, build) have topology-dependent command line interfaces, we
    # parse what's available so far to get that topology's name.
    action_subparsers = parser.add_subparsers(dest='action')

    # Start by creating parsers for each action we support (i.e. build, ssh, start). We also
    # add the minimum arguments needed by the parser to function (e.g. for the start action,
    # we need to know the topology to be able to load the correct topology.yaml).

    build_parser = action_subparsers.add_parser('build',
                                                formatter_class=FORMATTER_CLASS,
                                                add_help=False)
    build_parser.add_argument('-n', '--network',
                              help='Docker network to use',
                              default=defaults['DEFAULT_NETWORK'],
                              metavar='nw')
    build_parser.add_argument('-o', '--operating-system',
                              help='Operating system to use for cluster nodes',
                              metavar='sys')
    build_parser.add_argument('-r', '--repository',
                              help='Docker repository to use for committing images',
                              default=defaults['DEFAULT_REPOSITORY'],
                              metavar='url')

    build_parser.add_argument('topology',
                              help='A clusterdock topology directory')

    manage_parser = action_subparsers.add_parser('manage',
                                                 description='Manage clusterdock',
                                                 formatter_class=FORMATTER_CLASS,
                                                 add_help=False)

    ssh_parser = action_subparsers.add_parser('ssh',
                                              description='SSH into a cluster node',
                                              formatter_class=FORMATTER_CLASS,
                                              add_help=False)

    ps_parser = action_subparsers.add_parser('ps',
                                             description=('List clusterdock containers'),
                                             formatter_class=FORMATTER_CLASS,
                                             add_help=False)


    cp_parser = action_subparsers.add_parser('cp',
                                             description=('Copy files/folders between nodes or '
                                                          'between node and host filesystem'),
                                             formatter_class=FORMATTER_CLASS,
                                             add_help=False)

    start_parser = action_subparsers.add_parser('start',
                                                formatter_class=FORMATTER_CLASS,
                                                add_help=False)
    start_parser.add_argument('--always-pull',
                              help="Pull latest images, even if they're available locally",
                              action='store_true')
    start_parser.add_argument('-c', '--cluster-name',
                              help='Cluster name to use',
                              metavar='name')
    start_parser.add_argument('--namespace',
                              help='Namespace to use when looking for images',
                              metavar='ns')
    start_parser.add_argument('-n', '--network',
                              help='Docker network to use',
                              default=defaults['DEFAULT_NETWORK'],
                              metavar='nw')
    start_parser.add_argument('-o', '--operating-system',
                              help='Operating system to use for cluster nodes',
                              metavar='sys')
    start_parser.add_argument('-p', '--port',
                              help=('Publish node port to the host. The format should be "<node name>:<node port>" '
                                    'or "<node name>:<host port>-><node port>" (surrounding quotes are required). '
                                    'Argument may be used more than once for multiple ports.'),
                              metavar='port',
                              action='append')
    start_parser.add_argument('-r', '--registry',
                              help='Docker Registry from which to pull images',
                              default=defaults['DEFAULT_REGISTRY'],
                              metavar='url')
    start_parser.add_argument('topology',
                              help='A clusterdock topology directory')

    # Parse known args the second time to figure out which action the user wants to do and,
    # if it supports it, which topology to use.
    args, unknown_args = parser.parse_known_args()
    logger.debug('Parsed known args (%s) and found unknown args (%s).',
                 '; '.join('{}="{}"'.format(k, v) for k, v in vars(args).items()),
                 '; '.join(unknown_args))

    # We can now add a -h/--help argument to the top-level parser without affecting the ability to
    # get help once a topology is selected.
    _add_help(parser)

    # Manage parser
    # ~~~~~~~~~~~~~
    _add_help(manage_parser)
    manage_parser.add_argument('--dry-run',
                               action='store_true',
                               help="Don't actually perform manage actions")
    manage_subparsers = manage_parser.add_subparsers(dest='manage_action')
    manage_subparsers.required = True

    nuke_parser = manage_subparsers.add_parser('nuke')
    nuke_parser.add_argument('-a', '--all',
                             help='Nuke all containers',
                             action='store_true')

    remove_parser = manage_subparsers.add_parser('remove')
    remove_parser.add_argument('-n', '--network',
                               help='Remove Docker network',
                               action='store_true')
    remove_parser.add_argument('clusters', nargs='+', metavar='cluster',
                               help='One or more clusters to remove')

    # SSH parser
    # ~~~~~~~~~~
    _add_help(ssh_parser)
    ssh_parser.add_argument('node',
                            help='FQDN of cluster node to which to connect')

    # Copy parser
    # ~~~~~~~~~~~
    _add_help(cp_parser)
    cp_parser.add_argument('source',
                           help=('Local or Node source file system path. '
                                 'E.g. SRC_PATH or Node FQDN:SRC_PATH'))
    cp_parser.add_argument('destination',
                           help=('Local or Node destination file system path. '
                                 'E.g. DEST_PATH or Node FQDN:DEST_PATH'))

    # ps parser
    # ~~~~~~~~~
    _add_help(ps_parser)

    if hasattr(args, 'topology'):
        # As a workaround for https://github.com/docker/for-mac/issues/2396, we write the /etc/localtime
        # into the clusterdock config directory, which can be mounted into containers.
        if not os.path.exists(CLUSTERDOCK_CONFIG_DIRECTORY):
            os.makedirs(CLUSTERDOCK_CONFIG_DIRECTORY)
        with open('/etc/localtime', 'rb') as etc_localtime:
            with open(os.path.join(CLUSTERDOCK_CONFIG_DIRECTORY, 'localtime'), 'wb') as clusterdock_localtime:
                clusterdock_localtime.write(etc_localtime.read())

        topology = os.path.basename(os.path.realpath(args.topology))

        topology_definition_filename = defaults.get('DEFAULT_TOPOLOGY_DEFINITION_FILENAME')
        with open(os.path.realpath(os.path.join(args.topology,
                                                topology_definition_filename))) as topology_file:
            topology_configs = yaml.load(topology_file.read())
            topology_name = topology_configs.get('name')

        # Build parser
        # ~~~~~~~~~~~~
        build_parser.description = ('Build images for the {} topology'.format(topology_name)
                                    if hasattr(args, 'topology')
                                    else 'Build images for the topology')
        _add_help(build_parser)
        _add_topology_action_args(parser=build_parser,
                                  action='build',
                                  topology_configs=topology_configs)

        # Start parser
        # ~~~~~~~~~~~~
        start_parser.description = 'Start a {} cluster'.format(topology_name)
        _add_help(start_parser)
        _add_topology_action_args(parser=start_parser,
                                  action='start',
                                  topology_configs=topology_configs)

        node_group_argument_group = start_parser.add_argument_group('Node groups')
        for node_group, default_nodes in topology_configs.get('node groups', {}).items():
            node_group_argument_group.add_argument('--{}'.format(node_group),
                                                   help='Nodes of the {} group'.format(node_group),
                                                   nargs='+',
                                                   metavar='node',
                                                   default=default_nodes)
            logger.debug('Adding node group argument (%s) with default values (%s) ...',
                         node_group,
                         default_nodes)

    args = parser.parse_args()
    logger.debug('Parsed args (%s).',
                 '; '.join('{}="{}"'.format(k, v) for k, v in vars(args).items()))

    if not args.action:
        parser.print_help()
        parser.exit()

    models.clusterdock_args = args

    action = importlib.import_module('clusterdock.actions.{}'.format(args.action))
    action.main(args)


def _add_topology_action_args(parser, action, topology_configs):
    """Adds arguments for an action to a parser based on values from a topology configuration.

    Args:
        parser (:py:obj:`argparse.ArgumentParser`): Parser instance.
        action (:obj:`str`): Action that precedes ' args' in topology.yaml file.
        topology_configs (:obj:`dict`): Dictionary parsed from a topology.yaml file.
    """
    action_configs = topology_configs.get('{} args'.format(action), {})
    group = parser.add_argument_group('{} arguments'.format(topology_configs.get('name',
                                                                                 'Topology')))
    for arg_name, arg_parameters in action_configs.items():
        arg_names = arg_name.replace(' ', '').split(',')
        group.add_argument(*arg_names, **arg_parameters)
        logger.debug('Adding %s with parameters (%s) ...',
                     ('argument ({})'.format(arg_names[0])
                      if len(arg_names) == 1
                      else 'arguments ({})'.format(', '.join(arg_names))),
                     '; '.join('{}="{}"'.format(k, v) for k, v in arg_parameters.items()))


def _add_help(parser):
    """Utility method that adds a help argument to whichever parser is passed to it. This is
    needed to correctly handle display of help messages through the various parsers we create
    dynamically at runtime.

    Args:
        parser (:py:obj:`argparse.ArgumentParser`): Parser instance.
    """
    parser.add_argument('-h', '--help',
                        action='help',
                        default=argparse.SUPPRESS,
                        help='show this help message and exit')
