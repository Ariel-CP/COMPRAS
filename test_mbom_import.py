#!/usr/bin/env python3
"""Test script for MBOM async import endpoints."""
import requests
import json
import time

BASE_URL = 'http://127.0.0.1:8000'

def test_mbom_import():
    # 1. Login
    print("=" * 60)
    print("1. TESTING LOGIN")
    print("=" * 60)
    login_resp = requests.post(
        f'{BASE_URL}/api/auth/login',
        json={'email': 'admin@admin.com', 'password': 'admin'}
    )
    print(f"Login status: {login_resp.status_code}")
    if login_resp.status_code != 200:
        print(f"Login failed: {login_resp.text}")
        return
    
    login_data = login_resp.json()
    access_token = login_data.get('access_token')
    print(f"Access token obtained: {access_token[:30]}..." if access_token else "NO TOKEN")
    
    headers = {'Authorization': f'Bearer {access_token}'}
    
    # 2. Get list of MBOM
    print("\n" + "=" * 60)
    print("2. TESTING MBOM LIST")
    print("=" * 60)
    resp = requests.get(f'{BASE_URL}/api/mbom', headers=headers)
    print(f"MBOM list status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        items = data.get('items', [])
        print(f"MBOM count: {len(items)}")
        if items:
            print(f"First MBOM: {items[0]}")
    else:
        print(f"Error: {resp.text}")
    
    # 3. Check if job endpoints exist
    print("\n" + "=" * 60)
    print("3. TESTING JOB ENDPOINTS")
    print("=" * 60)
    
    # Get a list of products to import for
    resp_prods = requests.get(f'{BASE_URL}/api/productos?limit=100', headers=headers)
    if resp_prods.status_code == 200:
        prods = resp_prods.json().get('items', [])
        if prods:
            prod_id = prods[0].get('id')
            print(f"Using product ID: {prod_id}")
            
            # Try to start an import (will fail without file, but tests endpoint exists)
            print(f"\nAttempting to start async import for product {prod_id}...")
            import_start = requests.post(
                f'{BASE_URL}/api/mbom/{prod_id}/importar-flexxus-async',
                headers=headers,
                files={'archivo': ('test.csv', b'nivel,codigo,nombre,cantidad,unidad\n0,TEST,Test,1,UN')}
            )
            print(f"Async import start status: {import_start.status_code}")
            print(f"Response: {import_start.text[:500]}")
            
            if import_start.status_code == 202:
                data = import_start.json()
                job_id = data.get('job_id')
                print(f"\nJob started! ID: {job_id}")
                
                # Check status endpoint
                print(f"\nChecking job status...")
                for i in range(5):
                    status_resp = requests.get(
                        f'{BASE_URL}/api/mbom/import-status/{job_id}',
                        headers=headers
                    )
                    print(f"Status attempt {i+1}: {status_resp.status_code}")
                    if status_resp.status_code == 200:
                        status = status_resp.json()
                        print(f"  Estado: {status.get('estado')}")
                        print(f"  Porcentaje: {status.get('porcentaje')}%")
                        print(f"  Mensaje: {status.get('mensaje')}")
                    time.sleep(0.5)
    else:
        print(f"Could not get products: {resp_prods.status_code}")

if __name__ == '__main__':
    test_mbom_import()
