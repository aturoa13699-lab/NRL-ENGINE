"""
Historical scrape CLI entrypoint.

Usage: python -m nrlscraper.historical 1998 2025
"""

import sys

from nrlscraper.cli import main

if __name__ == '__main__':
    # Insert 'historical' command
    sys.argv = [sys.argv[0], 'historical'] + sys.argv[1:]
    main()
