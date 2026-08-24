#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests
import json

# Get repo info
print("Obteniendo información del repositorio pbir.tools...")
repo_url = "https://api.github.com/repos/maxanatsko/pbir.tools"
release_url = "https://api.github.com/repos/maxanatsko/pbir.tools/releases/latest"
readme_url = "https://raw.githubusercontent.com/maxanatsko/pbir.tools/main/README.md"

try:
    # Repo info
    r = requests.get(repo_url, timeout=10)
    if r.status_code == 200:
        data = r.json()
        print("\n=== REPOSITORIO ===")
        print(f"Nombre: {data.get('full_name')}")
        print(f"Descripción: {data.get('description', 'N/A')}")
        print(f"Lenguaje principal: {data.get('language', 'N/A')}")
        print(f"Stars: {data.get('stargazers_count', 0)}")
        print(f"Forks: {data.get('forks_count', 0)}")
        print(f"Última actualización: {data.get('updated_at', 'N/A')}")
        print(f"Homepage: {data.get('homepage', 'N/A')}")

    # Latest release
    r = requests.get(release_url, timeout=10)
    if r.status_code == 200:
        data = r.json()
        print("\n=== ÚLTIMA RELEASE ===")
        print(f"Versión: {data.get('tag_name', 'N/A')}")
        print(f"Nombre: {data.get('name', 'N/A')}")
        print(f"Publicado: {data.get('published_at', 'N/A')}")
        print(f"\nDescripción:")
        print(data.get('body', 'N/A')[:800])
        print("\nArchivos descargables:")
        for asset in data.get('assets', []):
            size_mb = asset['size'] / (1024 * 1024)
            print(f"  - {asset['name']} ({size_mb:.2f} MB)")
            print(f"    Descargas: {asset['download_count']}")

    # README
    r = requests.get(readme_url, timeout=10)
    if r.status_code == 200:
        print("\n=== README (primeras líneas) ===")
        lines = r.text.split('\n')[:30]
        print('\n'.join(lines))

except Exception as e:
    print(f"Error: {e}")
