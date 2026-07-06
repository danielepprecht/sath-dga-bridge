#!/usr/bin/env python3
"""
SATH DGA Bridge — fetch_dga.py
Extrae datos en tiempo real de la red hidrométrica DGA (SNIA/MOP)
para las estaciones SATH de Los Ríos y Los Lagos.

Credenciales: variables de entorno DGA_USER y DGA_PASS
              (GitHub Secrets → usadas en el workflow)

Salida: docs/dga_losrios.json  (servido por GitHub Pages)
"""

import os, sys, json, re, time, traceback
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

# ── Configuración ─────────────────────────────────────────────
DGA_BASE   = "https://snia.mop.gob.cl/dgasat"
LOGIN_PAGE = f"{DGA_BASE}/pages/dgasat_login/dgasat_login.htm"
DATA_PAGE  = f"{DGA_BASE}/pages/dgasat_param/dgasat_param.jsp"

# 12 estaciones SATH con sus códigos DGA
SATH_STATIONS = {
    "antihue":    {"codigo": "10122002", "nombre": "Rio Calle Calle En Antilhue",           "cuenca": "Calle-Calle",    "lat": -39.85, "lon": -73.10},
    "rinihue":    {"codigo": "10111001", "nombre": "Rio San Pedro En Desague Lago Rinihue",  "cuenca": "San Pedro",      "lat": -39.79, "lon": -72.43},
    "mamalona":   {"codigo": "10113003", "nombre": "Rio San Pedro En Pucono",                "cuenca": "San Pedro",      "lat": -39.58, "lon": -72.18},
    "valdivia":   {"codigo": "10134001", "nombre": "Rio Cruces En Rucaco",                   "cuenca": "Cruces",         "lat": -39.64, "lon": -73.09},
    "corral":     {"codigo": "10200001", "nombre": "Meteorologica Corral",                   "cuenca": "Costero",        "lat": -39.88, "lon": -73.43},
    "lacpicada":  {"codigo": "10133000", "nombre": "Rio Leufucade En Purulon",               "cuenca": "Cruces",         "lat": -39.82, "lon": -73.27},
    "laslomas":   {"codigo": "10411002", "nombre": "Rio Negro En Las Lomas",                 "cuenca": "Bueno-sur",      "lat": -39.94, "lon": -73.02},
    "tegualda":   {"codigo": "10351001", "nombre": "Rio Toro En Tegualda",                   "cuenca": "San Pedro",      "lat": -40.17, "lon": -72.62},
    "panguipulli":{"codigo": "10107003", "nombre": "Canal Hueninca En Desague Lago Calafquen","cuenca": "Calle-Calle",   "lat": -39.64, "lon": -72.33},
    "pilmaiquen": {"codigo": "10328001", "nombre": "Rio Pilmaiquen En San Pablo",            "cuenca": "Bueno-Ranco",    "lat": -40.18, "lon": -72.37},
    "launion":    {"codigo": "10313001", "nombre": "Rio Llollelhue En La Union",             "cuenca": "Bueno",          "lat": -40.29, "lon": -73.09},
    "riobueno":   {"codigo": "10311001", "nombre": "Rio Bueno En Bueno",                     "cuenca": "Bueno",          "lat": -40.69, "lon": -72.97},
}

OUTPUT_FILE = "docs/dga_losrios.json"

# ── Sesión HTTP ────────────────────────────────────────────────
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (SATH-DGA-Bridge/1.0; contacto: SATH)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-CL,es;q=0.9",
})


def login(user: str, password: str) -> bool:
    """Autenticar en DGA DGASAT. Retorna True si exitoso."""
    try:
        # Obtener página de login para extraer form action y campos ocultos
        r = session.get(LOGIN_PAGE, timeout=20, verify=False)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "lxml")
        form = soup.find("form")
        if not form:
            print("  ⚠ No se encontró formulario de login")
            return False

        action = form.get("action", "")
        if not action.startswith("http"):
            # Ruta relativa → construir URL absoluta
            base = LOGIN_PAGE.rsplit("/", 1)[0]
            action = f"{base}/{action.lstrip('/')}"

        # Recopilar campos ocultos del formulario
        payload = {}
        for inp in form.find_all("input"):
            name  = inp.get("name", "")
            value = inp.get("value", "")
            if name:
                payload[name] = value

        # Identificar campos de usuario/contraseña por nombre o posición
        fields = list(form.find_all("input"))
        user_fields = [f for f in fields if any(
            k in f.get("name","").lower() for k in ["user","usu","login","nombre"])]
        pass_fields = [f for f in fields if any(
            k in f.get("name","").lower() for k in ["pass","contra","clave","pwd"])]
        # Si no coinciden por nombre, usar primeros campos de tipo text/password
        if not user_fields:
            user_fields = [f for f in fields if f.get("type","text") == "text"]
        if not pass_fields:
            pass_fields = [f for f in fields if f.get("type","") == "password"]

        if user_fields:
            payload[user_fields[0].get("name","usuario")] = user
        if pass_fields:
            payload[pass_fields[0].get("name","contrasena")] = password

        print(f"  POST {action}")
        r2 = session.post(action, data=payload, timeout=20, verify=False, allow_redirects=True)
        r2.raise_for_status()

        # Verificar si el login fue exitoso (buscar indicadores de sesión activa)
        login_ok = any([
            "dgasat_param" in r2.url,
            "cerrar" in r2.text.lower(),
            "salir" in r2.text.lower(),
            "logout" in r2.text.lower(),
            "bienvenido" in r2.text.lower(),
        ])
        if not login_ok:
            # Intentar acceder a página protegida para verificar sesión
            r3 = session.get(f"{DGA_BASE}/pages/dgasat_param/dgasat_param.jsp?param=1",
                            timeout=15, verify=False)
            login_ok = "login" not in r3.url.lower()

        print(f"  Login {'✓ exitoso' if login_ok else '✗ fallido'}")
        return login_ok

    except Exception as e:
        print(f"  ✗ Error en login: {e}")
        return False


def fetch_station_realtime(codigo: str) -> dict:
    """Obtiene datos en tiempo real de una estación."""
    result = {"q_m3s": None, "nivel_m": None, "pp_mm": None,
              "fecha_dato": None, "estado": "sin_dato"}
    try:
        # Intentar diferentes URL patterns del DGASAT
        urls_to_try = [
            f"{DGA_BASE}/pages/dgasat_param/dgasat_param.jsp?param=1&cod_estacion={codigo}",
            f"{DGA_BASE}/pages/dgasat_param/dgasat_param_show.jsp?codigo_estacion={codigo}",
            f"{DGA_BASE}/pages/dgasat_param/dgasat_param.jsp?codigo={codigo}&param=1",
        ]

        html = None
        for url in urls_to_try:
            try:
                r = session.get(url, timeout=15, verify=False)
                if r.status_code == 200 and len(r.text) > 200:
                    if "login" not in r.url.lower():
                        html = r.text
                        break
            except:
                continue

        if not html:
            return result

        soup = BeautifulSoup(html, "lxml")

        # Buscar tablas con datos numéricos (caudal, nivel, precip)
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            for row in rows:
                cells = [td.get_text(strip=True) for td in row.find_all(["td","th"])]
                text  = " ".join(cells).lower()

                # Detectar caudal
                if any(k in text for k in ["caudal","m3/s","m³/s"]):
                    for cell in cells:
                        try:
                            v = float(cell.replace(",",".").replace(" ",""))
                            if 0 <= v <= 50000:
                                result["q_m3s"]  = round(v, 3)
                                result["estado"] = "ok"
                        except: pass

                # Detectar nivel
                if any(k in text for k in ["nivel","altura","msnm"]):
                    for cell in cells:
                        try:
                            v = float(cell.replace(",",".").replace(" ",""))
                            if 0 <= v <= 10000:
                                result["nivel_m"] = round(v, 3)
                        except: pass

                # Detectar precipitación
                if any(k in text for k in ["precip","lluvia","mm"]):
                    for cell in cells:
                        try:
                            v = float(cell.replace(",",".").replace(" ",""))
                            if 0 <= v <= 1000 and v != 999.9:
                                result["pp_mm"] = round(v, 1)
                        except: pass

                # Detectar fecha/hora
                date_patterns = [
                    r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}",
                    r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}",
                    r"\d{2}-\d{2}-\d{4} \d{2}:\d{2}",
                ]
                for cell in cells:
                    for pat in date_patterns:
                        m = re.search(pat, cell)
                        if m:
                            result["fecha_dato"] = m.group()
                            break

    except Exception as e:
        result["estado"] = f"error: {str(e)[:60]}"

    return result


def fetch_fallback_bnaconsultas(codigo: str) -> dict:
    """
    Fallback: obtiene último dato disponible desde BNAConsultas (público).
    Limitado a datos históricos (no tiempo real) pero funciona sin auth.
    """
    result = {"q_m3s": None, "nivel_m": None, "pp_mm": None,
              "fecha_dato": None, "estado": "fallback_bna"}
    try:
        # BNAConsultas tiene un endpoint de altura/caudal instantáneo
        # que a veces expone los últimos datos sin auth completa
        url = (f"https://snia.mop.gob.cl/BNAConsultas/reportes/generate"
               f"?type=fluviometrico&report=caudal&codigo={codigo}"
               f"&format=json")
        r = requests.get(url, timeout=15, verify=False,
                        headers={"Accept": "application/json"})
        if r.status_code == 200:
            try:
                data = r.json()
                # Extraer último valor disponible
                if isinstance(data, list) and data:
                    last = data[-1]
                    result["q_m3s"]     = last.get("caudal") or last.get("value")
                    result["fecha_dato"]= last.get("fecha") or last.get("date")
                    result["estado"]    = "fallback_ok"
            except:
                pass
    except:
        pass
    return result


def build_output(results: dict, login_ok: bool) -> dict:
    """Construye el JSON final para SATH."""
    now_utc  = datetime.now(timezone.utc)
    now_cl   = now_utc.astimezone(timezone(timedelta(hours=-4)))  # UTC-4 Chile

    n_ok = sum(1 for v in results.values() if v.get("estado") == "ok")

    return {
        "meta": {
            "timestamp_utc":   now_utc.isoformat(),
            "timestamp_chile": now_cl.isoformat(),
            "fuente":          "DGA — Sistema Hidrométrico Nacional (SNIA/MOP)",
            "url_fuente":      "https://snia.mop.gob.cl/dgasat/",
            "aviso":           "Datos provisorios sujetos a revisión — DGA/MOP",
            "login_ok":        login_ok,
            "n_estaciones_ok": n_ok,
            "n_estaciones":    len(SATH_STATIONS),
            "prox_actualizacion": (now_utc + timedelta(hours=1)).isoformat(),
        },
        "estaciones": results
    }


def main():
    print(f"{'='*60}")
    print(f"SATH DGA Bridge — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}")

    # Suprimir advertencias SSL (certificados DGA a veces caducos)
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    user = os.environ.get("DGA_USER", "")
    pwd  = os.environ.get("DGA_PASS", "")

    login_ok = False
    if user and pwd:
        print(f"\n[1/3] Autenticando en DGA DGASAT ({user})...")
        login_ok = login(user, pwd)
    else:
        print("\n[1/3] Sin credenciales DGA — modo fallback público")

    print(f"\n[2/3] Extrayendo datos de {len(SATH_STATIONS)} estaciones...")
    results = {}
    for stn_id, stn in SATH_STATIONS.items():
        print(f"  {stn['codigo']} {stn['nombre'][:35]:<35}", end=" ")
        if login_ok:
            data = fetch_station_realtime(stn["codigo"])
        else:
            data = fetch_fallback_bnaconsultas(stn["codigo"])

        # Combinar metadata de estación con datos
        results[stn_id] = {
            "codigo":     stn["codigo"],
            "nombre":     stn["nombre"],
            "cuenca":     stn["cuenca"],
            "lat":        stn["lat"],
            "lon":        stn["lon"],
            **data
        }
        estado_icon = "✓" if data["estado"] == "ok" else "~" if "fallback" in data["estado"] else "✗"
        q_str = f"Q={data['q_m3s']}m³/s" if data["q_m3s"] is not None else "Q=—"
        print(f"[{estado_icon}] {q_str}")
        time.sleep(0.5)  # cortesía al servidor DGA

    print(f"\n[3/3] Guardando JSON → {OUTPUT_FILE}")
    output = build_output(results, login_ok)
    os.makedirs("docs", exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    n_ok = output["meta"]["n_estaciones_ok"]
    print(f"\n✓ Completado: {n_ok}/{len(SATH_STATIONS)} estaciones con dato")
    print(f"  Archivo: {OUTPUT_FILE} ({os.path.getsize(OUTPUT_FILE)} bytes)")

    # Exit code 0 siempre (no fallar el workflow por datos faltantes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
