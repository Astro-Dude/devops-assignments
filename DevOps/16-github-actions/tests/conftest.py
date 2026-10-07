import os
import sys

# make "import app" work no matter where pytest is started from
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
