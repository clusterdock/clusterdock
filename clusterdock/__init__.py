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

import colorlog

__author__ = """Dima Spivak"""
__email__ = 'dima@spivak.ch'
__version__ = '1.5.0'

formatter = colorlog.ColoredFormatter(
    (
        '%(asctime)s '
        '[%(log_color)s%(levelname)s%(reset)s] '
        '[%(cyan)s%(name)s%(reset)s] '
        '%(message_log_color)s%(message)s'
    ),
    reset=True,
    log_colors={
        'DEBUG': 'bold_cyan',
        'INFO': 'bold_green',
        'WARNING': 'bold_yellow',
        'ERROR': 'bold_red',
        'CRITICAL': 'bold_red,bg_white',
    },
    secondary_log_colors={
        'message': {
            'DEBUG': 'white',
            'INFO': 'bold_white',
            'WARNING': 'bold_yellow',
            'ERROR': 'bold_red',
            'CRITICAL': 'bold_red',
        },
    },
    style='%'
)
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logging.getLogger(__name__).addHandler(handler)
