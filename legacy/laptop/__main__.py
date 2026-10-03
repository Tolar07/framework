import sys
import os
# Change to the parent directory (olp_xdv_agent) where the pipeline script expects to run
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
# Add the current directory to the Python path
sys.path.insert(0, os.getcwd())
from olp_xdv_pipeline import main
if __name__ == '__main__':
    main()
