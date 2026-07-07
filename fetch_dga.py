#!/usr/bin/env python3
"""
SATH DGA Bridge — fetch_dga.py v4 — VipNet API pública
Fuente: https://vipnet.mop.gob.cl/v1/vipnet/estaciones/valor
"""
import os, sys, json
from datetime import datetime, timezone, timedelta
import requests

VIPNET_URL = "https://vipnet.mop.gob.cl/v1/vipnet/estaciones/valor"
HEADERS = {
    "Accept":          "application/json, text/plain, */*",
    "Content-Type":    "application/json",
    "Origin":          "https://vipnet.mop.gob.cl",
    "Referer":         "https://vipnet.mop.gob.cl/",
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/149.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9",
}

SATH_STATIONS = {
    "10122002": "antihue",    "10111001": "rinihue",
    "10113003": "mamalona",   "10134001": "valdivia",
    "10200001": "corral",     "10133000": "lacpicada",
    "10411002": "laslomas",   "10351001": "tegualda",
    "10107003": "panguipulli","10328001": "pilmaiquen",
    "10313001": "launion",    "10311001": "riobueno",
}
SATH_META = {
    "antihue":     {"nombre":"Rio Calle Calle En Antilhue",            "cuenca":"Calle-Calle", "lat":-39.85,"lon":-73.10},
    "rinihue":     {"nombre":"Rio San Pedro En Desague Lago Rinihue",   "cuenca":"San Pedro",   "lat":-39.79,"lon":-72.43},
    "mamalona":    {"nombre":"Rio San Pedro En Pucono",                 "cuenca":"San Pedro",   "lat":-39.58,"lon":-72.18},
    "valdivia":    {"nombre":"Rio Cruces En Rucaco",                    "cuenca":"Cruces",      "lat":-39.64,"lon":-73.09},
    "corral":      {"nombre":"Meteorologica Corral",                    "cuenca":"Costero",     "lat":-39.88,"lon":-73.43},
    "lacpicada":   {"nombre":"Rio Leufucade En Purulon",                "cuenca":"Cruces",      "lat":-39.82,"lon":-73.27},
    "laslomas":    {"nombre":"Rio Negro En Las Lomas",                  "cuenca":"Bueno-sur",   "lat":-39.94,"lon":-73.02},
    "tegualda":    {"nombre":"Rio Toro En Tegualda",                    "cuenca":"San Pedro",   "lat":-40.17,"lon":-72.62},
    "panguipulli": {"nombre":"Canal Hueninca Lago Calafquen",           "cuenca":"Calle-Calle", "lat":-39.64,"lon":-72.33},
    "pilmaiquen":  {"nombre":"Rio Pilmaiquen En San Pablo",             "cuenca":"Bueno-Ranco", "lat":-40.18,"lon":-72.37},
    "launion":     {"nombre":"Rio Llollelhue En La Union",              "cuenca":"Bueno",       "lat":-40.29,"lon":-73.09},
    "riobueno":    {"nombre":"Rio Bueno En Bueno",                      "cuenca":"Bueno",       "lat":-40.69,"lon":-72.97},
}
OUTPUT = "docs/dga_losrios.json"


def get_numeric(item, *fields):
    for f in fields:
        v = item.get(f)
        if v is None:
            continue
        if isinstance(v, list):
            for sub in reversed(v):
                try:
                    fv = float(str(sub).replace(",","."))
                    if 0 <= fv < 50000 and fv != 999.9:
                        return round(fv, 3)
                except: pass
        else:
            try:
                fv = float(str(v).replace(",","."))
                if 0 <= fv < 50000 and fv != 999.9:
                    return round(fv, 3)
            except: pass
    return None


def get_text(item, *fields):
    for f in fields:
        v = item.get(f)
        if v: return str(v)
    return None


def extract_from_record(item):
    # Buscar en estructuras anidadas
    for nest_key in ("parametros","datos","valores","params","mediciones"):
        nested = item.get(nest_key)
        if not isinstance(nested, list) or not nested:
            continue
        q=None; pp=None; nv=None; fecha=None; var_name=""
        for param in nested:
            if not isinstance(param, dict): continue
            vname = str(param.get("nombre","") or param.get("variable","")).lower()
            val   = get_numeric(param,"value","valor","ultimo","ultimoValor","lastValue")
            fec   = get_text(param,"fecha","date","fechaHora","ultimaFecha","timestamp")
            if fec: fecha = fec
            if any(k in vname for k in ["caudal","q ","flujo","flow"]):
                if val is not None: q=val; var_name="Caudal"
            elif any(k in vname for k in ["precip","lluvia","pp"]):
                if val is not None: pp=val; var_name="Precipitación"
            elif any(k in vname for k in ["nivel","altura","height"]):
                if val is not None: nv=val; var_name="Nivel"
            else:
                if val is not None and q is None and pp is None and nv is None:
                    q=val; var_name=vname[:30]
        if any(x is not None for x in [q, pp, nv]):
            return q, pp, nv, fecha, var_name

    # Buscar directamente en el registro (campo "value" primero — estructura VipNet)
    q  = get_numeric(item,"value","valor","caudal","q","ultimoValor","lastValue","dato")
    pp = get_numeric(item,"precipitacion","pp","lluvia") if q is None else None
    nv = get_numeric(item,"nivel","altura","height")     if q is None else None
    fec = get_text(item,"fecha","date","fechaHora","ultimaFecha","fechaDato","timestamp")
    var = get_text(item,"variable","nombreVariable","tipoVariable","nombre") or "—"
    return q, pp, nv, fec, var


def main():
    now_utc = datetime.now(timezone.utc)
    now_cl  = now_utc.astimezone(timezone(timedelta(hours=-4)))

    print("="*65)
    print(f"SATH DGA Bridge v4 — VipNet · {now_cl.strftime('%Y-%m-%d %H:%M')} CL")
    print("="*65)

    print("\n[1/3] VipNet POST...")
    raw = []; ok = False
    for offset in [0, -1, -2]:
        dt = now_cl + timedelta(hours=offset)
        payload = {
            "tipoEstacion": 0, "mapStatistic": 4,
            "currentTabIndex": 0,
            "fetchHour": dt.hour,
            "fetchDay":  dt.strftime("%Y-%m-%d"),
            "hoursRange": 3,
        }
        try:
            r = requests.post(VIPNET_URL, json=payload, headers=HEADERS, timeout=30)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list):
                raw = data
            else:
                for k in ("estaciones","data","features","result","registros"):
                    if isinstance(data.get(k), list):
                        raw = data[k]; break
                if not raw:
                    raw = list(data.values())[0] if data else []
            print(f"  offset={offset}h → {r.status_code} "
                  f"{len(r.content)/1024:.1f}KB → {len(raw)} registros")
            if raw: ok = True; break
        except Exception as e:
            print(f"  offset={offset}h → ERROR: {e}")

    if not raw:
        print("  Sin respuesta de VipNet")
        _save_empty(now_utc, now_cl); return 0

    # DEBUG: mostrar primer registro para verificar estructura
    print(f"\n  DEBUG primer registro:")
    print(f"  {json.dumps(raw[0], ensure_ascii=False)[:400]}")

    print(f"\n[2/3] Extrayendo 12 estaciones SATH de {len(raw)} registros...")
    results = {}
    for item in raw:
        # FIX v4: VipNet devuelve "10122002-1" → extraer solo la parte numérica
        cod_raw = str(item.get("codigoEstacion","") or item.get("codigo","")).strip()
        cod = cod_raw.split("-")[0]   # "10122002-1" → "10122002"

        if cod not in SATH_STATIONS:
            # Intentar sin cero inicial como último recurso
            cod_s = cod.lstrip("0")
            cod = next((c for c in SATH_STATIONS if c.lstrip("0")==cod_s), None)
            if not cod: continue

        stn_id = SATH_STATIONS[cod]
        meta   = SATH_META[stn_id]
        q, pp, nv, fecha, var = extract_from_record(item)

        results[stn_id] = {
            "codigo":    cod,
            "nombre":    meta["nombre"],
            "cuenca":    meta["cuenca"],
            "lat":       meta["lat"],
            "lon":       meta["lon"],
            "q_m3s":     q,
            "pp_mm":     pp,
            "nivel_m":   nv,
            "fecha_dato":fecha,
            "variable":  var,
            "estado":    "ok" if any(x is not None for x in [q,pp,nv]) else "sin_valor",
        }
        icon = "✓" if results[stn_id]["estado"]=="ok" else "~"
        print(f"  [{icon}] {stn_id:<12} Q={q} PP={pp} NV={nv} var={var[:25]}")

    # Rellenar estaciones no encontradas
    for stn_id, meta in SATH_META.items():
        if stn_id not in results:
            cod = next(c for c,s in SATH_STATIONS.items() if s==stn_id)
            results[stn_id] = {
                "codigo":cod, "nombre":meta["nombre"], "cuenca":meta["cuenca"],
                "lat":meta["lat"], "lon":meta["lon"],
                "q_m3s":None, "pp_mm":None, "nivel_m":None,
                "fecha_dato":None, "variable":"—", "estado":"no_encontrado",
            }

    n_ok = sum(1 for v in results.values() if v["estado"]=="ok")
    print(f"\n  Estaciones con dato: {n_ok}/12")

    output = {
        "meta": {
            "timestamp_utc":      now_utc.isoformat(),
            "timestamp_chile":    now_cl.isoformat(),
            "fuente":             "VipNet — DGA/MOP (vipnet.mop.gob.cl)",
            "endpoint":           VIPNET_URL,
            "aviso":              "Datos provisorios sujetos a revisión — DGA/MOP",
            "fetch_ok":           ok,
            "n_estaciones_ok":    n_ok,
            "n_estaciones":       12,
            "n_raw_registros":    len(raw),
            "prox_actualizacion": (now_utc+timedelta(hours=1)).isoformat(),
        },
        "estaciones": results,
    }

    print(f"\n[3/3] Guardando → {OUTPUT}")
    os.makedirs("docs", exist_ok=True)
    with open(OUTPUT,"w",encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  ✓ {os.path.getsize(OUTPUT):,} bytes · {n_ok}/12 estaciones con dato")
    return 0


def _save_empty(now_utc, now_cl):
    os.makedirs("docs", exist_ok=True)
    with open(OUTPUT,"w") as f:
        json.dump({"meta":{"timestamp_utc":now_utc.isoformat(),
                           "fetch_ok":False,"n_estaciones_ok":0},
                   "estaciones":{}}, f, indent=2)


if __name__ == "__main__":
    sys.exit(main())
