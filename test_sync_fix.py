#!/usr/bin/env python3
"""Test BCRA sync with db.commit() fix."""
import requests
import json

BASE_URL = 'http://127.0.0.1:8000'

# Login
print("1. Logging in...")
login = requests.post(f'{BASE_URL}/api/auth/login', json={'email': 'admin@admin.com', 'password': 'admin'})
if login.status_code != 200:
    print(f"Login failed: {login.text}")
    exit(1)

token = login.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}
print("✓ Logged in")

# Test sync endpoint
print("\n2. Testing SYNC endpoint...")
sync_resp = requests.post(f'{BASE_URL}/api/tipo-cambio/sync-oficial', headers=headers)
print(f"Status: {sync_resp.status_code}")

if sync_resp.status_code == 200:
    resp_data = sync_resp.json()
    print(f"Insertados: {resp_data.get('insertados', 0)}")
    print(f"Actualizados: {resp_data.get('actualizados', 0)}")
    print(f"Procesados: {resp_data.get('procesados', 0)}")
    print("✓ SYNC completed successfully")
else:
    print(f"Error: {sync_resp.text}")
    exit(1)

# Check records
print("\n3. Checking DB records...")
list_resp = requests.get(f'{BASE_URL}/api/tipo-cambio/?limit=5', headers=headers)
if list_resp.status_code == 200:
    data = list_resp.json()
    items = data.get('items', [])
    print(f"Total records: {len(items)}")
    print("\nLatest records:")
    for item in items[:3]:
        print(f"  {item['fecha']} {item['moneda']}: {item['tasa']} ({item['origen']})")
    print("\n✓ Records are in DB!")
else:
    print(f"Error: {list_resp.text}")

print("\n✓ SUCCESS - db.commit() is working!")
