#!/usr/bin/env python
# -*- coding: utf-8 -*-
import subprocess
import csv
from io import StringIO
import sys

# Set stdout encoding to utf-8
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Run tasklist command
result = subprocess.run(
    ['tasklist', '/FI', 'IMAGENAME eq PBIDesktop.exe', '/V', '/FO', 'CSV'],
    capture_output=True,
    text=True,
    encoding='utf-8',
    errors='replace'
)

with open('test_output.txt', 'w', encoding='utf-8') as f:
    f.write(f"Return code: {result.returncode}\n")
    f.write(f"Output length: {len(result.stdout)}\n")
    f.write("\n--- CSV Output ---\n")
    f.write(result.stdout)
    f.write("\n--- Parsed Data ---\n")

    csv_reader = csv.DictReader(StringIO(result.stdout))
    for i, row in enumerate(csv_reader):
        f.write(f"\nRow {i+1}:\n")
        f.write(f"  Keys: {list(row.keys())}\n")

        # Try both Spanish and English column names
        window_title = row.get('Título de ventana', row.get('Window Title', '')).strip()
        f.write(f"  Raw window title: [{window_title}]\n")

        if window_title and window_title not in ['N/A', 'No aplicable', '']:
            # Clean the title
            clean_title = window_title.replace(' - Power BI Desktop', '').replace('*', '').strip()
            f.write(f"  Clean title: [{clean_title}]\n")
            f.write(f"  ✓ WOULD USE THIS NAME\n")
            print(f"DETECTED FILE: {clean_title}")
        else:
            f.write(f"  ✗ Skipped (invalid title)\n")

print("Test complete. Check test_output.txt for details.")
