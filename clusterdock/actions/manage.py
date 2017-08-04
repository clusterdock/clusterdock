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

import docker

logger = logging.getLogger(__name__)

client = docker.from_env()


def main(args):
    if args.dry_run:
        logger.warning('All manage actions will be done in dry-run mode.')

    if args.manage_action == 'nuke':
        if client.containers.list():
            logger.info('Stopping and removing all containers ...')
            for container in client.containers.list(all=True):
                logger.debug('Removing container %s ...',
                             container.id)
                if not args.dry_run:
                    container.remove(v=True, force=True)
        else:
            logger.warning("Didn't find any containers to remove. Continuing ...")

        # Since we don't know whether any networks were removed until after we loop through them
        # with our try-except block, keep track of them as we go and only display logging info
        # after the fact.
        removed_networks = []
        for network in client.networks.list():
            try:
                network.remove()
                removed_networks.append(network.name)
            except docker.errors.APIError as api_error:
                if 'is a pre-defined network and cannot be removed' not in api_error.explanation:
                    raise api_error
        if removed_networks:
            logger.info('Removing all user-defined networks ...')
            for network in removed_networks:
                logger.debug('Removing network %s ...',
                             network)
        else:
            logger.warning("Didn't find any user-defined networks to remove. Continuing ...")
