#!/usr/bin/env python3
"""Test BCRA sync endpoint directly."""
import requests
import json

BASE = 'http://127.0.0.1:8000'

print("=" * 70)
print("TEST 1: Sync endpoint (no auth required)")
print("=" * 70)
r = requests.post(f'{BASE}/api/tipo-cambio/sync-oficial')
print(f"Status: {r.status_code}")
try:
    data = r.json()
    print(json.dumps(data, indent=2))
    if r.status_code == 200:
        print(f"\n✓ Sync successful!")
        print(f"  Insertados: {data.get('insertados', 0)}")
        print(f"  Actualizados: {data.get('actualizados', 0)}")
        print(f"  Procesados: {data.get('procesados', 0)}")
except Exception as e:
    print(f"Error: {e}")
    print(f"Response: {r.text[:500]}")

print("\n" + "=" * 70)
print("TEST 2: Get tipo-cambio list to verify data was saved")
print("=" * 70)

# Get list without auth (might fail if auth required)
r2 = requests.get(f'{BASE}/api/tipo-cambio')
print(f"Status: {r2.status_code}")
if r2.status_code == 200:
    data2 = r2.json()
    items = data2.get('items', [])
    print(f"✓ Found {len(items)} records in DB")
    if items:
        print("\nLatest records:")
        for item in items[:3]:
            print(f"  {item.get('fecha')} {item.get('moneda')} {item.get('tipo')}: {item.get('tasa')} ({item.get('origen')})")
else:
    print(f"Response: {r2.text[:300]}")

print("\n" + "=" * 70)
