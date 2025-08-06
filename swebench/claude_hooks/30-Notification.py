#!/usr/bin/env python3
"""Hook for heartbeat notifications (stall detection)."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from logship import main
main()