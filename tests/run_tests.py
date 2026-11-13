"""Run the tests inside a background Blender.

    blender --background --factory-startup --python tests/run_tests.py
    blender --background --factory-startup --python tests/run_tests.py -- orient flipped

Names after `--` pick test files (`orient` runs test_orient.py); without names every
test file runs. Blender exits with 0 when everything passed and 1 otherwise.

A background Blender has no UV editor, so Relax can only be checked for what does not
depend on one (see test_relax.py)."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

names = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
loader = unittest.TestLoader()
suite = unittest.TestSuite()
if names:
    for n in names:
        suite.addTests(loader.discover(HERE, pattern=f"test_{n}.py", top_level_dir=HERE))
else:
    suite.addTests(loader.discover(HERE, pattern="test_*.py", top_level_dir=HERE))

result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.stdout.flush()
sys.exit(0 if result.wasSuccessful() else 1)
