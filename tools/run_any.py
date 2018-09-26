# Copyright 2018 the Deno authors. All rights reserved. MIT license.
"""
gn can only run python scripts. This script launches any other executable.
"""

import util
import sys

util.run(sys.argv[1:], quiet=True, shell=False)
