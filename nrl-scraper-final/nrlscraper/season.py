"""
Season scrape CLI entrypoint.

Usage: python -m nrlscraper.season 2024
"""
import sys
from nrlscraper.cli import main

if __name__ == '__main__':
    # Insert 'season' command
    sys.argv = [sys.argv[0], 'season'] + sys.argv[1:]
    main()
