"""QBR Dashboard loader entry point.

Implementation lives in load_data_v2.py. The production command remains:
    python load_data.py --replace-tickets
"""
from load_data_v2 import main

if __name__ == "__main__":
    main()
