#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import requests
import json

# Configure proxy
os.environ['HTTPS_PROXY'] = 'http://proxy-azure'
os.environ['HTTP_PROXY'] = 'http://proxy-azure'

proxies = {
    'http': 'http://proxy-azure',
    'https': 'http://proxy-azure'
}

print("Obteniendo información del repositorio pbir.tools con proxy...")

try:
    # Repo info
    print("\n=== REPOSITORIO ===")
    r = requests.get(
        "https://api.github.com/repos/maxanatsko/pbir.tools",
        proxies=proxies,
        timeout=30
    )
    if r.status_code == 200:
        data = r.json()
        print(f"Nombre: {data.get('full_name')}")
        print(f"Descripción: {data.get('description', 'N/A')}")
        print(f"Lenguaje principal: {data.get('language', 'N/A')}")
        print(f"Stars: {data.get('stargazers_count', 0)}")
        print(f"Forks: {data.get('forks_count', 0)}")
        print(f"Issues abiertos: {data.get('open_issues_count', 0)}")
        print(f"Última actualización: {data.get('updated_at', 'N/A')}")
        print(f"Creado: {data.get('created_at', 'N/A')}")
        print(f"Homepage: {data.get('homepage', 'N/A')}")
        print(f"Licencia: {data.get('license', {}).get('name', 'N/A')}")
    else:
        print(f"Error obteniendo repo info: {r.status_code}")

    # Latest release
    print("\n=== ÚLTIMA RELEASE ===")
    r = requests.get(
        "https://api.github.com/repos/maxanatsko/pbir.tools/releases/latest",
        proxies=proxies,
        timeout=30
    )
    if r.status_code == 200:
        data = r.json()
        print(f"Versión: {data.get('tag_name', 'N/A')}")
        print(f"Nombre: {data.get('name', 'N/A')}")
        print(f"Publicado: {data.get('published_at', 'N/A')}")
        print(f"\nDescripción de la release:")
        print("-" * 60)
        print(data.get('body', 'N/A'))
        print("-" * 60)
        print("\n📦 Archivos descargables:")
        for asset in data.get('assets', []):
            size_mb = asset['size'] / (1024 * 1024)
            print(f"\n  - {asset['name']}")
            print(f"    Tamaño: {size_mb:.2f} MB")
            print(f"    Descargas: {asset['download_count']}")
            print(f"    URL: {asset['browser_download_url']}")
    else:
        print(f"Error obteniendo release info: {r.status_code}")

    # README
    print("\n=== README ===")
    r = requests.get(
        "https://raw.githubusercontent.com/maxanatsko/pbir.tools/main/README.md",
        proxies=proxies,
        timeout=30
    )
    if r.status_code == 200:
        print("-" * 60)
        print(r.text)
        print("-" * 60)
    else:
        print(f"Error obteniendo README: {r.status_code}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
