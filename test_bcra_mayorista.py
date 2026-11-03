#!/usr/bin/env python
"""Verificar si BCRA tiene endpoint para dólar mayorista."""

import httpx

endpoints = [
    '/estadisticascambiarias/v1.0/Cotizaciones/USDMAY',
    '/estadisticascambiarias/v1.0/Cotizaciones/USD_MAY',
    '/estadisticascambiarias/v1.0/Cotizaciones/Mayorista',
]

base_url = 'https://api.bcra.gob.ar'
params = {
    'fechadesde': '2026-08-01',
    'fechahasta': '2026-08-31',
}

for endpoint in endpoints:
    url = base_url + endpoint
    try:
        resp = httpx.get(url, params=params, timeout=10)
        print(f'✓ {endpoint}: HTTP {resp.status_code}')
        if resp.status_code == 200:
            data = resp.json()
            # Verificar si hay datos
            if isinstance(data, dict) and 'results' in data:
                print(f'  → Encontrados {len(data["results"])} resultados')
                if data['results']:
                    print(f'  → Primer resultado: {data["results"][0]}')
            break
    except Exception as e:
        print(f'✗ {endpoint}: {e}')
