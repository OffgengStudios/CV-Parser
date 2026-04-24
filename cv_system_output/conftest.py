"""
conftest.py — pytest session configuration.

Sets TESTING=true before any app module is imported so that the
Settings.enforce_strong_secret_key validator is skipped during the
test run (tests use the default dev SECRET_KEY by design).
"""
import os

# Must be set before any import of config.py / Settings
os.environ.setdefault("TESTING", "true")
