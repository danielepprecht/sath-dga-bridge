#!/usr/bin/env python3
"""
SATH DGA Bridge — fetch_dga.py  (v2 — VipNet API pública)
Fuente: https://vipnet.mop.gob.cl/v1/vipnet/estaciones/valor
Sin credenciales. POST con fecha/hora actual → JSON de todas las estaciones.
Salida: docs/dga_losrios.json  (servido por GitHub Pages)
"""
 
import os, sys, json, time
from datetime import datetime, timezone, timedelta
import requests
 
# ── Endpoint VipNet (público, sin autenticación) ───────────────
VIPNET_URL = "https://vipnet.mop.gob.cl/v1/vipnet/estaciones/valor"
 
HEADERS = {
    "Accept":           "application/json, text/plain, */*",
    "Content-Type":     "application/json",
    "Origin":           "https://vipnet.mop.gob.cl",
    "Referer":          "https://vipnet.mop.gob.cl/",
    "User-Agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/149.0.0.0 Safari/537.36",
    "Accept-Language":  "es-ES,es;q=0.9",
}
 
# 12 estaciones SATH → código DGA como clave de búsqueda
SATH_STATIONS = {
    "10122002": "antihue",
    "10111001": "rinihue",
    "10113003": "mamalona",
    "10134001": "valdivia",
    "10200001": "corral",
    "10133000": "lacpicada",
    "10411002": "laslomas",
    "10351001": "tegualda",
    "10107003": "panguipulli",
    "10328001": "pilmaiquen",
    "10313001": "launion",
    "10311001": "riobueno",
}
 
SATH_META = {
    "antihue":     {"nombre": "Rio Calle Calle En Antilhue",            "cuenca": "Calle-Calle",  "lat": -39.85, "lon": -73.10},
    "rinihue":     {"nombre": "Rio San Pedro En Desague Lago Rinihue",   "cuenca": "San Pedro",    "lat": -39.79, "lon": -72.43},
    "mamalona":    {"nombre": "Rio San Pedro En Pucono",                 "cuenca": "San Pedro",    "lat": -39.58, "lon": -72.18},
    "valdivia":    {"nombre": "Rio Cruces En Rucaco",                    "cuenca": "Cruces",       "lat": -39.64, "lon": -73.09},
    "corral":      {"nombre": "Meteorologica Corral",                    "cuenca": "Costero",      "lat": -39.88, "lon": -73.43},
    "lacpicada":   {"nombre": "Rio Leufucade En Purulon",                "cuenca": "Cruces",       "lat": -39.82, "lon": -73.27},
    "laslomas":    {"nombre": "Rio Negro En Las Lomas",                  "cuenca": "Bueno-sur",    "lat": -39.94, "lon": -73.02},
    "tegualda":    {"nombre": "Rio Toro En Tegualda",                    "cuenca": "San Pedro",    "lat": -40.17, "lon": -72.62},
    "panguipulli": {"nombre": "Canal Hueninca En Desague Lago Calafquen","cuenca": "Calle-Calle",  "lat": -39.64, "lon": -72.33},
    "pilmaiquen":  {"nombre": "Rio Pilmaiquen En San Pablo",             "cuenca": "Bueno-Ranco",  "lat": -40.18, "lon": -72.37},
    "launion":     {"nombre": "Rio Llollelhue En La Union",              "cuenca": "Bueno",        "lat": -40.29, "lon": -73.09},
    "riobueno":    {"nombre": "Rio Bueno En Bueno",                      "cuenca": "Bueno",        "lat": -40.69, "lon": -72.97},
}
 
OUTPUT = "docs/dga_losrios.json"
 
 
def build_payload(dt_cl: datetime) -> dict:
    """Construye el payload exacto que usa VipNet en el browser."""
    return {
        "tipoEstacion":    0,          # 0 = todas las estaciones
        "mapStatistic":    4,          # 4 = Más Actual
        "currentTabIndex": 0,
        "fetchHour":       dt_cl.hour,
        "fetchDay":        dt_cl.strftime("%Y-%m-%d"),
        "hoursRange":      3,          # ventana de ±3h para el dato más reciente
    }
 
 
def fetch_vipnet(dt_cl: datetime) -> list:
    """Llama a VipNet y retorna la lista de estaciones con sus valores."""
    payload = build_payload(dt_cl)
    print(f"  POST {VIPNET_URL}")
    print(f"  Payload: {json.dumps(payload)}")
 
    r = requests.post(VIPNET_URL, json=payload, headers=HEADERS, timeout=30)
    r.raise_for_status()
 
    data = r.json()
    print(f"  Respuesta: {r.status_code} — {len(r.content)/1024:.1f} KB")
 
    # La respuesta puede ser lista directa o dict con clave de datos
    if isinstance(data, list):
        return data
    # Buscar clave que contenga la lista de estaciones
    for key in ("estaciones", "data", "valores", "features", "result"):
        if key in data and isinstance(data[key], list):
            return data[key]
    # Último recurso: devolver todos los valores de la respuesta
    print(f"  Estructura respuesta: {list(data.keys()) if isinstance(data, dict) else type(data)}")
    return []
 
 
def parse_stations(raw: list) -> dict:
    """
    Extrae valores para las 12 estaciones SATH desde la respuesta VipNet.
    Busca por código DGA en cualquier campo que lo contenga.
    """
    results = {}
 
    for item in raw:
        if not isinstance(item, dict):
            continue
 
        # Detectar código DGA en distintos campos posibles
        codigo = None
        for field in ("codigo", "code", "cod_estacion", "codigoEstacion",
                      "id", "estacion_id", "stationCode"):
            v = str(item.get(field, "")).strip().lstrip("0")
            if v in [c.lstrip("0") for c in SATH_STATIONS]:
                # Normalizar a 8 dígitos con ceros
                codigo = v.zfill(8)
                break
            # También probar con ceros originales
            v2 = str(item.get(field, "")).strip()
            if v2 in SATH_STATIONS:
                codigo = v2
                break
 
        if not codigo or codigo not in SATH_STATIONS:
            continue
 
        stn_id = SATH_STATIONS[codigo]
        meta   = SATH_META[stn_id]
 
        # Extraer valor numérico (Q, nivel o PP)
        q_val = None
        for field in ("valor", "value", "caudal", "q", "nivel", "height",
                      "ultimoValor", "lastValue", "datos"):
            v = item.get(field)
            if v is not None:
                try:
                    fv = float(str(v).replace(",", "."))
                    if fv != 999.9 and fv >= 0:
                        q_val = round(fv, 3)
                        break
                except (ValueError, TypeError):
                    pass
 
        # Extraer fecha del dato
        fecha = None
        for field in ("fecha", "date", "datetime", "fechaHora",
                      "fechaDato", "timestamp", "ultimaFecha"):
            v = item.get(field)
            if v:
                fecha = str(v)
                break
 
        # Detectar tipo de variable (caudal vs precipitación vs nivel)
        variable = str(item.get("variable", item.get("nombreVariable", ""))).lower()
        is_q  = any(k in variable for k in ["caudal", "q ", "flujo", "flow"])
        is_pp = any(k in variable for k in ["precip", "lluvia", "pp"])
        is_nv = any(k in variable for k in ["nivel", "height", "altura"])
 
        results[stn_id] = {
            "codigo":     codigo,
            "nombre":     meta["nombre"],
            "cuenca":     meta["cuenca"],
            "lat":        meta["lat"],
            "lon":        meta["lon"],
            "q_m3s":      q_val if is_q  or (not is_pp and not is_nv) else None,
            "pp_mm":      q_val if is_pp else None,
            "nivel_m":    q_val if is_nv else None,
            "fecha_dato": fecha,
            "variable":   str(item.get("variable", item.get("nombreVariable", "—"))),
            "estado":     "ok" if q_val is not None else "sin_dato",
            "raw_keys":   list(item.keys())[:8],  # debug: campos disponibles
        }
        print(f"    ✓ {stn_id:<12} {meta['nombre'][:35]:<35} "
              f"val={q_val} var={variable[:20]}")
 
    return results
 
 
def fill_missing(results: dict) -> dict:
    """Agrega estaciones SATH no encontradas con estado sin_dato."""
    for stn_id, meta in SATH_META.items():
        if stn_id not in results:
            cod = next(c for c, s in SATH_STATIONS.items() if s == stn_id)
            results[stn_id] = {
                "codigo": cod, "nombre": meta["nombre"],
                "cuenca": meta["cuenca"], "lat": meta["lat"], "lon": meta["lon"],
                "q_m3s": None, "pp_mm": None, "nivel_m": None,
                "fecha_dato": None, "variable": "—", "estado": "no_encontrado",
            }
    return results
 
 
def main():
    now_utc = datetime.now(timezone.utc)
    now_cl  = now_utc.astimezone(timezone(timedelta(hours=-4)))
 
    print("=" * 65)
    print(f"SATH DGA Bridge v2 — VipNet API")
    print(f"Fecha/hora Chile: {now_cl.strftime('%Y-%m-%d %H:%M')}  "
          f"(UTC: {now_utc.strftime('%H:%M')})")
    print("=" * 65)
 
    # ── Fetch VipNet ─────────────────────────────────────────────
    print("\n[1/3] Consultando VipNet MOP (público, sin credenciales)...")
    raw  = []
    ok   = False
    err  = ""
 
    # Intentar hora actual, luego hora anterior como fallback
    for hora_offset in [0, -1, -2]:
        dt_try = now_cl + timedelta(hours=hora_offset)
        try:
            raw = fetch_vipnet(dt_try)
            if raw:
                ok = True
                break
        except Exception as e:
            err = str(e)
            print(f"  ✗ offset {hora_offset}h: {err[:80]}")
 
    print(f"\n  Total registros recibidos: {len(raw)}")
    if raw:
        # Mostrar muestra de la estructura para debug
        sample = raw[0] if raw else {}
        print(f"  Campos en primer registro: {list(sample.keys())[:10]}")
 
    # ── Parsear ───────────────────────────────────────────────────
    print(f"\n[2/3] Extrayendo 12 estaciones SATH...")
    results = parse_stations(raw)
    results = fill_missing(results)
 
    n_ok = sum(1 for v in results.values() if v["estado"] == "ok")
    print(f"\n  Estaciones con dato: {n_ok}/12")
 
    # ── Guardar JSON ─────────────────────────────────────────────
    output = {
        "meta": {
            "timestamp_utc":     now_utc.isoformat(),
            "timestamp_chile":   now_cl.isoformat(),
            "fuente":            "VipNet — DGA/MOP (vipnet.mop.gob.cl)",
            "endpoint":          VIPNET_URL,
            "aviso":             "Datos provisorios sujetos a revisión — DGA/MOP",
            "fetch_ok":          ok,
            "n_estaciones_ok":   n_ok,
            "n_estaciones":      12,
            "n_raw_registros":   len(raw),
            "prox_actualizacion": (now_utc + timedelta(hours=1)).isoformat(),
        },
        "estaciones": results,
    }
 
    print(f"\n[3/3] Guardando → {OUTPUT}")
    os.makedirs("docs", exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
 
    print(f"  ✓ {os.path.getsize(OUTPUT):,} bytes")
    print(f"\n{'✓ COMPLETADO' if n_ok > 0 else '⚠ SIN DATOS — revisar estructura respuesta'}")
    return 0
 
 
if __name__ == "__main__":
    sys.exit(main())
