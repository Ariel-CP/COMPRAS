#!/usr/bin/env python
"""Test: endpoints de sincronización multi-moneda."""
import httpx
import json

BASE_URL = "http://localhost:8000/api/tipo-cambio"

print("=" * 70)
print("TEST: API Endpoints Sincronización Multi-Moneda")
print("=" * 70)

# Test 1: Endpoint histórico con USD
print("\n[TEST 1] POST /sync-historico con USD")
print("-" * 70)
response = httpx.post(
    f"{BASE_URL}/sync-historico",
    params={
        "fecha_desde": "2026-08-28",
        "fecha_hasta": "2026-08-30",
        "monedas": "USD",
    }
)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"Respuesta:")
    print(f"  Recibidos: {data['recibidos']}")
    print(f"  Insertados: {data['insertados']}")
    print(f"  Actualizados: {data['actualizados']}")
    print(f"  Sin cambios: {data['sin_cambios']}")
    print(f"  Errores: {data['errores']}")
else:
    print(f"Error: {response.text}")

# Test 2: Endpoint histórico con múltiples monedas
print("\n[TEST 2] POST /sync-historico con USD,USD_MAY")
print("-" * 70)
response = httpx.post(
    f"{BASE_URL}/sync-historico",
    params={
        "fecha_desde": "2026-08-28",
        "fecha_hasta": "2026-08-30",
        "monedas": "USD,USD_MAY",
    }
)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"Respuesta:")
    print(f"  Recibidos: {data['recibidos']}")
    print(f"  Insertados: {data['insertados']}")
    print(f"  Actualizados: {data['actualizados']}")
    print(f"  Sin cambios: {data['sin_cambios']}")
    print(f"  Errores: {data['errores']}")
else:
    print(f"Error: {response.text}")

# Test 3: Endpoint incremental con múltiples monedas
print("\n[TEST 3] POST /sync-historico-incremental con USD,USD_MAY")
print("-" * 70)
response = httpx.post(
    f"{BASE_URL}/sync-historico-incremental",
    params={
        "monedas": "USD,USD_MAY",
    }
)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"Respuesta:")
    print(f"  Recibidos: {data['recibidos']}")
    print(f"  Insertados: {data['insertados']}")
    print(f"  Actualizados: {data['actualizados']}")
    print(f"  Sin cambios: {data['sin_cambios']}")
    print(f"  Errores: {data['errores']}")
else:
    print(f"Error: {response.text}")

print("\n" + "=" * 70)
print("Tests completados")
print("=" * 70)
