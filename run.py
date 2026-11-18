#!/usr/bin/env python3
"""
Devengers Mail Engine Entry Point
Run the web dashboard: python3 run.py web
Inspect quota/status:   python3 run.py status
Import contacts:        python3 run.py import contacts.xlsx
Dispatch emails:        python3 run.py send
"""
import sys
from devengers_engine.cli import main

if __name__ == "__main__":
    if len(sys.argv) == 1:
        # Default to web dashboard when run with no arguments
        sys.argv.append("web")
    main()
