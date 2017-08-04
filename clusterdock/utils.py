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

import operator
from functools import reduce


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
