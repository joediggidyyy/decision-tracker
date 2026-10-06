"""Compatibility import for the former planning-application module."""
import sys
from . import planning_links
sys.modules[__name__] = planning_links
