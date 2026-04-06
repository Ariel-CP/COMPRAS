#!/usr/bin/env python3
r"""Pruebas dinámicas básicas para el sistema de login.
- POST /auth/login
- Verifica Set-Cookie flags
- Lista /auth/sessions, revoca y comprueba acceso
- Mide tiempo para enumeración (usuario inexistente vs contraseña errónea)

Ejecutar: .venv\Scripts\python.exe scripts\auth_dynamic_tests.py
"""

import requests  # type: ignore[import-untyped]
import time
import sys

BASE = "http://127.0.0.1:8000/api"


def try_login(email, password, remember=False):
    s = requests.Session()
    url = f"{BASE}/auth/login"
    payload = {"email": email, "password": password, "remember_me": remember}
    start = time.time()
    r = s.post(url, json=payload)
    elapsed = time.time() - start
    return r, s, elapsed


def print_set_cookie_info(r):
    sc = r.headers.get("set-cookie")
    print("  Set-Cookie:", sc)
    if not sc:
        return
    print("   - HttpOnly:", "httponly".lower() in sc.lower())
    print("   - Secure:", "secure".lower() in sc.lower())
    print("   - SameSite:", "samesite".lower() in sc.lower() and ("lax" in sc.lower() or "strict" in sc.lower()))


def main():
    print("== Prueba básica de login ==")
    r, s, t = try_login("admin@example.com", "admin123", remember=True)
    print("Login status:", r.status_code)
    try:
        print("Body:", r.json())
    except Exception:
        print("Body (raw):", r.text[:400])
    print_set_cookie_info(r)

    if r.status_code == 200:
        # listar sesiones
        r2 = s.get(f"{BASE}/auth/sessions")
        print("GET /auth/sessions ->", r2.status_code)
        try:
            sessions = r2.json()
        except Exception:
            sessions = None
        print(" Sessions:", sessions)
        # revocar primera sesión si existe
        if sessions and isinstance(sessions, list) and len(sessions) > 0:
            jti = sessions[0].get("jti")
            print(" Revocando jti:", jti)
            r3 = s.delete(f"{BASE}/auth/sessions/{jti}")
            print(" DELETE session ->", r3.status_code)
            # intentar /auth/me
            r4 = s.get(f"{BASE}/auth/me")
            print(" GET /auth/me after revoke ->", r4.status_code)
            try:
                print(" me body:", r4.json())
            except Exception:
                print(" me raw:", r4.text[:300])

    print('\n== Prueba de enumeración y timings ==')
    # inexistente
    r_a, _, t_a = try_login("noexiste-xyz@example.com", "whatever")
    print("Nonexistent user ->", r_a.status_code, "time=", round(t_a, 3))
    # existe pero pass incorrecta
    r_b, _, t_b = try_login("admin@example.com", "wrong-pass-123")
    print("Existing user wrong pass ->", r_b.status_code, "time=", round(t_b, 3))

    print('\n== Intentos fallidos repetidos (brute force) ==')
    for i in range(6):
        r_try, _, _ = try_login("admin@example.com", f"badpass{i}")
        print(f" attempt {i+1}: {r_try.status_code}")

    print('\n== Fin pruebas dinámicas ==')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('Error ejecutando pruebas:', exc)
        sys.exit(2)
