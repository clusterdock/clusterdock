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

"""This module contains clusterdock exceptions."""


class DuplicateClusterNameError(Exception):
    def __init__(self, name, clusters):
        self.name = name
        self.clusters = sorted(clusters)

    def __str__(self):
        return ('Found duplicate cluster name ({}). '
                'Clusters found ({})'.format(self.name, ', '.join(self.clusters)))


class DuplicateHostnamesError(Exception):
    def __init__(self, duplicates, network):
        self.duplicates = sorted(duplicates)
        self.network = network

    def __str__(self):
        return 'Found duplicate hostnames ({}) on network ({}).'.format(', '.join(self.duplicates),
                                                                        self.network)


class NodeNotFoundError(Exception):
    def __init__(self, node):
        self.node = node

    def __str__(self):
        return 'Could not find node {}.'.format(self.node)
