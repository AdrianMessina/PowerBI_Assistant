#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import requests

os.environ['HTTPS_PROXY'] = 'http://proxy-azure'
os.environ['HTTP_PROXY'] = 'http://proxy-azure'

proxies = {
    'http': 'http://proxy-azure',
    'https': 'http://proxy-azure'
}

print("Verificando licencia de pbir.tools...\n")

try:
    # Get license info
    r = requests.get(
        "https://api.github.com/repos/maxanatsko/pbir.tools",
        proxies=proxies,
        timeout=30
    )

    if r.status_code == 200:
        data = r.json()
        license_info = data.get('license')

        if license_info:
            print(f"Licencia detectada: {license_info.get('name', 'N/A')}")
            print(f"SPDX ID: {license_info.get('spdx_id', 'N/A')}")
            print(f"Key: {license_info.get('key', 'N/A')}")
            print(f"URL: {license_info.get('url', 'N/A')}")
        else:
            print("No se encontró información de licencia en los metadatos del repo")

        # Try to get LICENSE file
        print("\n--- Intentando obtener archivo LICENSE ---")
        r2 = requests.get(
            "https://raw.githubusercontent.com/maxanatsko/pbir.tools/main/LICENSE",
            proxies=proxies,
            timeout=30
        )

        if r2.status_code == 200:
            print("\nContenido del archivo LICENSE:")
            print("=" * 70)
            print(r2.text[:2000])  # First 2000 chars
            print("=" * 70)
        else:
            # Try LICENSE.md
            r3 = requests.get(
                "https://raw.githubusercontent.com/maxanatsko/pbir.tools/main/LICENSE.md",
                proxies=proxies,
                timeout=30
            )
            if r3.status_code == 200:
                print("\nContenido del archivo LICENSE.md:")
                print("=" * 70)
                print(r3.text[:2000])
                print("=" * 70)
            else:
                print(f"\nNo se encontró archivo LICENSE (status: {r2.status_code}, {r3.status_code})")

        # Check PyPI for license info
        print("\n--- Verificando PyPI (pip package) ---")
        r4 = requests.get(
            "https://pypi.org/pypi/pbir-cli/json",
            proxies=proxies,
            timeout=30
        )

        if r4.status_code == 200:
            pypi_data = r4.json()
            info = pypi_data.get('info', {})
            print(f"Licencia en PyPI: {info.get('license', 'N/A')}")
            print(f"Classifiers:")
            for classifier in info.get('classifiers', []):
                if 'License' in classifier:
                    print(f"  - {classifier}")
            print(f"\nHomepage: {info.get('home_page', 'N/A')}")
            print(f"Author: {info.get('author', 'N/A')}")
            print(f"Última versión: {info.get('version', 'N/A')}")
        else:
            print(f"No se pudo acceder a PyPI (status: {r4.status_code})")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
