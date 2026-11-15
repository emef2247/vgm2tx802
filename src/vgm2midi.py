#!/usr/bin/env python3
"""Compatibility entry point; source analysis uses the current MSX musical layer."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.export_tx802 import main
if __name__ == '__main__':
    raise SystemExit(main())
