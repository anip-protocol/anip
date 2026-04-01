"""Pytest configuration for anip-server tests."""
import sys
import os

# Ensure the tests directory is on sys.path so non-package imports work
sys.path.insert(0, os.path.dirname(__file__))
