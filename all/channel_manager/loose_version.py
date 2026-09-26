"""Keep the former distutils LooseVersion ordering without distutils."""

import re
from functools import total_ordering


@total_ordering
class LooseVersion:
    component_re = re.compile(r'(\d+ | [a-z]+ | \.)', re.VERBOSE)

    def __init__(self, vstring=None):
        if vstring:
            self.parse(vstring)

    def parse(self, vstring):
        self.vstring = vstring
        components = [part for part in self.component_re.split(vstring)
                      if part and part != '.']
        for index, part in enumerate(components):
            try:
                components[index] = int(part)
            except ValueError:
                pass
        self.version = components

    def __str__(self):
        return self.vstring

    def __repr__(self):
        return "LooseVersion ('%s')" % self

    def _cmp(self, other):
        if isinstance(other, str):
            other = LooseVersion(other)
        elif not isinstance(other, LooseVersion):
            return NotImplemented

        if self.version == other.version:
            return 0
        if self.version < other.version:
            return -1
        return 1

    def __eq__(self, other):
        result = self._cmp(other)
        return result if result is NotImplemented else result == 0

    def __lt__(self, other):
        result = self._cmp(other)
        return result if result is NotImplemented else result < 0
