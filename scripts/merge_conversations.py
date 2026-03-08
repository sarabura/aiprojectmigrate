#!/usr/bin/env python3
# Author: Martin Sarabura (martin.sarabura@gmail.com)
# License: MIT
# Repository: https://github.com/sarabura/aiprojectmigrate
# Issues and improvement requests: https://github.com/sarabura/aiprojectmigrate/issues
"""
merge_conversations.py

Merges multiple ChatGPT data export JSON files into a single file.

ChatGPT splits large exports into multiple files named conversations-000.json,
conversations-001.json, etc. This script loads each file as a valid JSON array
and combines them into a single conversations_merged.json without the encoding
or concatenation issues that simpler approaches produce.

Usage:
    python3 merge_conversations.py

    By default, merges all files matching conversations-0*.json in the current
    directory and writes conversations_merged.json.

Options:
    --output    Output filename (default: conversations_merged.json)
    --dir       Directory to search (default: current directory)
"""

import json
import glob
import argparse
import os
import sys


def parse_args():
    p = argparse.ArgumentParser(description="Merge ChatGPT export JSON files.")
    p.add_argument("--output", default="conversations_merged.json",
                   help="Output filename (default: conversations_merged.json)")
    p.add_argument("--dir", default=".",
                   help="Directory to search (default: current directory)")
    return p.parse_args()


def main():
    args = parse_args()

    pattern = os.path.join(args.dir, "conversations-0*.json")
    files = sorted(glob.glob(pattern))

    if not files:
        print(f"ERROR: No files found matching: {pattern}", file=sys.stderr)
        print("       Check the --dir option or verify your export files are present.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(files)} file(s):")
    combined = []

    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, list):
                print(f"  WARNING: {f} does not contain a JSON array -- skipping.")
                continue
            print(f"  {f}: {len(data)} conversations")
            combined.extend(data)
        except json.JSONDecodeError as e:
            print(f"  ERROR: Could not parse {f}: {e}", file=sys.stderr)
            sys.exit(1)
        except UnicodeDecodeError as e:
            print(f"  ERROR: Encoding problem in {f}: {e}", file=sys.stderr)
            print("         Try re-exporting from ChatGPT.", file=sys.stderr)
            sys.exit(1)

    output_path = os.path.join(args.dir, args.output)
    print(f"\nTotal: {len(combined)} conversations")

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(combined, fh, ensure_ascii=False)

    print(f"Written to: {output_path}")


if __name__ == "__main__":
    main()
