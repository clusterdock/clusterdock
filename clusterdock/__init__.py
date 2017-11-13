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

"""Top-level package for clusterdock."""

import logging

__author__ = """Dima Spivak"""
__email__ = 'dima@spivak.ch'
__version__ = '1.3.2'

handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s %(name)-20s %(levelname)-8s %(message)s',
                                       '%Y-%m-%d %I:%M:%S %p'))
logging.getLogger(__name__).addHandler(handler)
