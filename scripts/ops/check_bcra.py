"""Prueba manual para consultar la API pública del BCRA y mostrar una cotización USD.

Ejecutar:
    .venv\Scripts\python.exe scripts\ops\check_bcra.py

"""
from datetime import date
from app.services.fx_provider import BcraFxProvider


def main():
    provider = BcraFxProvider()
    from datetime import timedelta
    hoy = date.today()
    desde = hoy - timedelta(days=7)
    try:
        raw = provider._request_usd()
        print("RAW RESPONSE:", raw)
        tasas = provider.fetch_range(desde, hoy)
        if not tasas:
            print("No se obtuvieron tasas para hoy")
            return
        for t in tasas:
            print("Fecha:", t.fecha)
            print("Moneda:", t.moneda)
            print("Tasa:", t.tasa)
            print("Origen:", t.origen)
            print("Notas:", t.notas)
            print("---")
    except Exception as exc:
        import traceback
        print("Error consultando BCRA:")
        traceback.print_exc()
    finally:
        provider.close()


if __name__ == '__main__':
    main()
