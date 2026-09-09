#!/usr/bin/env python
"""Pruebas exhaustivas de BCRA API para encontrar endpoint del mayorista."""
import httpx
import json
from datetime import date

BASE_URL = "https://api.bcra.gob.ar/estadisticascambiarias/v1.0"

print("=" * 80)
print("BÚSQUEDA: Endpoint BCRA para dólar mayorista (USD_MAY)")
print("=" * 80)

# 1. Probar el endpoint USD estándar
print("\n[1] Cotizaciones/USD (control)")
print("-" * 80)
try:
    resp = httpx.get(f"{BASE_URL}/Cotizaciones/USD", timeout=10)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"✓ OK - Estructura: {json.dumps(data, indent=2)[:500]}")
    else:
        print(f"✗ Error: {resp.text[:200]}")
except Exception as e:
    print(f"✗ Excepción: {e}")

# 2. Probar variantes de nombres para mayorista
endpoints = [
    "/Cotizaciones/USDMAY",
    "/Cotizaciones/USD_MAY",
    "/Cotizaciones/Mayorista",
    "/Cotizaciones/USD/Mayorista",
    "/CotizacionesMayorista/USD",
]

print("\n[2] Intentar variantes de endpoint para mayorista")
print("-" * 80)
for endpoint in endpoints:
    try:
        resp = httpx.get(f"{BASE_URL}{endpoint}", timeout=5)
        print(f"{endpoint:40} → Status {resp.status_code}")
    except Exception as e:
        print(f"{endpoint:40} → Error: {type(e).__name__}")

# 3. Intentar con parámetros diferentes en USD
print("\n[3] Parámetros alternativos en /Cotizaciones/USD")
print("-" * 80)
params_variants = [
    {"tipo": "mayorista"},
    {"moneda": "USD_MAY"},
    {"moneda": "USDMAY"},
    {"mercado": "mayorista"},
    {"mercado": "oficial"},
    {"tipoCotizacion": "mayorista"},
]

for params in params_variants:
    try:
        resp = httpx.get(f"{BASE_URL}/Cotizaciones/USD", params=params, timeout=5)
        print(f"Params {str(params):40} → Status {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            if results:
                print(f"  → Monedas encontradas: ", end="")
                monedas = set()
                for r in results:
                    for d in r.get("detalle", []):
                        monedas.add(d.get("descripcion", "?"))
                print(", ".join(monedas))
    except Exception as e:
        print(f"Params {str(params):40} → Excepción: {type(e).__name__}")

# 4. Listar todas las variables disponibles
print("\n[4] Intentar /Variables (endpoint de listado)")
print("-" * 80)
try:
    resp = httpx.get(f"{BASE_URL}/Variables", timeout=10)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"✓ OK - Encontradas variables:")
        for var in data.get("results", [])[:10]:
            print(f"  - {var}")
    else:
        print(f"✗ No encontrado: {resp.status_code}")
except Exception as e:
    print(f"✗ Error: {e}")

# 5. Probar endpoint de monedas
print("\n[5] Intentar /Monedas (endpoint de listado)")
print("-" * 80)
try:
    resp = httpx.get(f"{BASE_URL}/Monedas", timeout=10)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"✓ OK - Monedas disponibles:")
        for var in data.get("results", []):
            print(f"  - {var}")
    else:
        print(f"✗ No encontrado")
except Exception as e:
    print(f"✗ Error: {e}")

# 6. Intentar estructura de historias/periodos
print("\n[6] Intentar /Cotizaciones con parámetros de fechas amplios")
print("-" * 80)
try:
    resp = httpx.get(
        f"{BASE_URL}/Cotizaciones",
        params={
            "fechadesde": "2026-01-01",
            "fechahasta": "2026-08-31",
        },
        timeout=10,
    )
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"✓ OK - Estructura:")
        print(json.dumps(data, indent=2)[:500])
    else:
        print(f"✗ Error: {resp.text[:200]}")
except Exception as e:
    print(f"✗ Error: {e}")

print("\n" + "=" * 80)
print("Análisis completado")
print("=" * 80)
