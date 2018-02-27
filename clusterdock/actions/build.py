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
    topology = os.path.basename(os.path.realpath(args.topology))
    sys.path.append(os.path.dirname(os.path.realpath(args.topology)))
    logger.debug('PYTHONPATH: %s', sys.path)
    action = importlib.import_module('{}.{}'.format(topology, args.action))
    build_start_time = datetime.datetime.now()
    action.main(args)
    build_delta = relativedelta(datetime.datetime.now(), build_start_time)
    logger.info('Build successful (total time: %sm %ss).',
                build_delta.minutes,
                build_delta.seconds)
