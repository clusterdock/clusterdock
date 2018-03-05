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

import datetime
import importlib
import logging
import os
import sys
from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)


def main(args):
    topology_name = args.topology
    topology = os.path.basename(os.path.realpath(topology_name))
    sys.path.append(os.path.dirname(os.path.realpath(topology_name)))
    logger.debug('PYTHONPATH: %s', sys.path)
    action = importlib.import_module('{}.{}'.format(topology, args.action))
    start_cluster_start_time = datetime.datetime.now()
    action.main(args)
    start_cluster_delta = relativedelta(datetime.datetime.now(), start_cluster_start_time)
    logger.info('Cluster started successfully (total time: %sm %ss).',
                start_cluster_delta.minutes,
                start_cluster_delta.seconds)
