#!/usr/bin/env python3
"""SATH DGA Bridge v8 — VipNet API — mapeo final con proxies región 14"""
import os, sys, json
from datetime import datetime, timezone, timedelta
import requests

VIPNET_URL = "https://vipnet.mop.gob.cl/v1/vipnet/estaciones/valor"
HEADERS = {
    "Accept":          "application/json, text/plain, */*",
    "Content-Type":    "application/json",
    "Origin":          "https://vipnet.mop.gob.cl",
    "Referer":         "https://vipnet.mop.gob.cl/",
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "es-ES,es;q=0.9",
}

# Mapeo definitivo: código VipNet → id SATH
# 4 estaciones directas + 4 proxies geográficos confirmados en región 14
SATH_STATIONS = {
    # Confirmadas activas con código original
    "10200001": "corral",
    "10133000": "lacpicada",
    "10313001": "launion",
    "10328001": "pilmaiquen",
    # Proxies VipNet región 14 para estaciones sin telemetría directa
    "10111015": "rinihue",      # Lago Riñihue Estacion de Control
    "10327006": "riobueno",     # Escuela Rural Crucero (cuenca Río Bueno)
    "10307009": "panguipulli",  # Futrono Sector Las Quemas (cuenca Lago Ranco)
    "10304011": "mamalona",     # Fundo Sichahue (cuenca San Pedro/Calcurrupe)
    # Sin telemetría en VipNet — mantienen metadata pero Q=null
    "10122002": "antihue",
    "10134001": "valdivia",
    "10411002": "laslomas",
    "10351001": "tegualda",
}

SATH_META = {
    "antihue":     {"nombre":"Rio Calle Calle En Antilhue",                    "cuenca":"Calle-Calle", "lat":-39.85,"lon":-73.10},
    "rinihue":     {"nombre":"Lago Riñihue Estacion de Control [proxy]",        "cuenca":"San Pedro",   "lat":-39.79,"lon":-72.43},
    "mamalona":    {"nombre":"Fundo Sichahue - San Pedro [proxy]",              "cuenca":"San Pedro",   "lat":-39.58,"lon":-72.18},
    "valdivia":    {"nombre":"Rio Cruces En Rucaco",                            "cuenca":"Cruces",      "lat":-39.64,"lon":-73.09},
    "corral":      {"nombre":"Meteorologica Corral",                            "cuenca":"Costero",     "lat":-39.88,"lon":-73.43},
    "lacpicada":   {"nombre":"Rio Leufucade En Purulon",                        "cuenca":"Cruces",      "lat":-39.82,"lon":-73.27},
    "laslomas":    {"nombre":"Rio Negro En Las Lomas",                          "cuenca":"Bueno-sur",   "lat":-39.94,"lon":-73.02},
    "tegualda":    {"nombre":"Rio Toro En Tegualda",                            "cuenca":"San Pedro",   "lat":-40.17,"lon":-72.62},
    "panguipulli": {"nombre":"Futrono Sector Las Quemas - Lago Ranco [proxy]",  "cuenca":"Calle-Calle", "lat":-39.64,"lon":-72.33},
    "pilmaiquen":  {"nombre":"Rio Pilmaiquen En San Pablo",                     "cuenca":"Bueno-Ranco", "lat":-40.18,"lon":-72.37},
    "launion":     {"nombre":"Rio Llollelhue En La Union",                      "cuenca":"Bueno",       "lat":-40.29,"lon":-73.09},
    "riobueno":    {"nombre":"Escuela Rural Crucero - Cuenca Río Bueno [proxy]","cuenca":"Bueno",       "lat":-40.69,"lon":-72.97},
}
OUTPUT = "docs/dga_losrios.json"


def get_numeric(item, *fields):
    for f in fields:
        v = item.get(f)
        if v is None: continue
        if isinstance(v, list):
            for sub in reversed(v):
                try:
                    fv = float(str(sub).replace(",","."))
                    if 0 <= fv < 50000 and fv != 999.9: return round(fv,3)
                except: pass
        else:
            try:
                fv = float(str(v).replace(",","."))
                if 0 <= fv < 50000 and fv != 999.9: return round(fv,3)
            except: pass
    return None


def get_text(item, *fields):
    for f in fields:
        v = item.get(f)
        if v: return str(v)
    return None


def fetch_vipnet(dt, tipo):
    payload = {
        "tipoEstacion": tipo, "mapStatistic": 4,
        "currentTabIndex": 0,
        "fetchHour": dt.hour,
        "fetchDay":  dt.strftime("%Y-%m-%d"),
        "hoursRange": 3,
    }
    r = requests.post(VIPNET_URL, json=payload, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list): return data
    for k in ("estaciones","data","features","result","registros"):
        if isinstance(data.get(k), list): return data[k]
    return list(data.values())[0] if data else []


def extract_value(item):
    for nk in ("parametros","datos","valores","params","mediciones"):
        nested = item.get(nk)
        if not isinstance(nested, list): continue
        for p in nested:
            if not isinstance(p, dict): continue
            val = get_numeric(p,"value","valor","ultimo","ultimoValor")
            if val is not None:
                return val, get_text(p,"fecha","date","fechaHora"), get_text(p,"nombre","variable") or "—"
    val = get_numeric(item,"value","valor","caudal","q","ultimoValor")
    fec = get_text(item,"fecha","date","fechaHora","ultimaFecha","fechaDato")
    var = get_text(item,"nombre","variable","nombreVariable") or "—"
    return val, fec, var


def main():
    now_utc = datetime.now(timezone.utc)
    now_cl  = now_utc.astimezone(timezone(timedelta(hours=-4)))
    print("="*65)
    print(f"SATH DGA Bridge v8 — {now_cl.strftime('%Y-%m-%d %H:%M')} CL")
    print("="*65)

    # Fetch tipos 0-2 (los más ricos en datos)
    all_records = {}
    total_raw   = 0
    ok          = False

    for tipo in [0, 1, 2]:
        dt = now_cl
        try:
            raw = fetch_vipnet(dt, tipo)
            if not raw: continue
            total_raw += len(raw)
            ok = True
            nuevas = 0
            for item in raw:
                if not isinstance(item, dict): continue
                cod_raw = str(item.get("codigoEstacion","") or item.get("codigo","")).strip()
                cod = cod_raw.split("-")[0]
                if cod in SATH_STATIONS and cod not in all_records:
                    all_records[cod] = item
                    nuevas += 1
            print(f"  tipo={tipo} → {len(raw)} reg → nuevas: {nuevas} "
                  f"(total: {len(all_records)}/12)")
            if len(all_records) >= 8: break
        except Exception as e:
            print(f"  tipo={tipo} → ERROR: {e}")

    print(f"\n  Total registros: {total_raw} | SATH encontradas: {len(all_records)}/12")

    # Parsear estaciones encontradas
    print(f"\n[2/3] Parseando estaciones...")
    results = {}
    for cod, item in all_records.items():
        stn_id = SATH_STATIONS[cod]
        meta   = SATH_META[stn_id]
        val, fec, var = extract_value(item)
        es_proxy = "[proxy]" in meta["nombre"]
        results[stn_id] = {
            "codigo":     cod,
            "nombre":     meta["nombre"],
            "cuenca":     meta["cuenca"],
            "lat":        meta["lat"],
            "lon":        meta["lon"],
            "q_m3s":      val,
            "pp_mm":      None,
            "nivel_m":    None,
            "fecha_dato": fec,
            "variable":   var,
            "es_proxy":   es_proxy,
            "estado":     "ok" if val is not None else "sin_valor",
        }
        icon = "✓" if val is not None else "~"
        proxy_tag = " [proxy]" if es_proxy else ""
        print(f"  [{icon}] {stn_id:<12} Q={val} var={var[:25]}{proxy_tag}")

    # Rellenar estaciones sin telemetría
    for stn_id, meta in SATH_META.items():
        if stn_id not in results:
            cod = next(c for c,s in SATH_STATIONS.items() if s==stn_id)
            results[stn_id] = {
                "codigo":     cod,
                "nombre":     meta["nombre"],
                "cuenca":     meta["cuenca"],
                "lat":        meta["lat"],
                "lon":        meta["lon"],
                "q_m3s":      None,
                "pp_mm":      None,
                "nivel_m":    None,
                "fecha_dato": None,
                "variable":   "—",
                "es_proxy":   False,
                "estado":     "sin_telemetria",
            }
            print(f"  [—] {stn_id:<12} sin telemetría VipNet")

    n_ok = sum(1 for v in results.values() if v["estado"] == "ok")

    # Guardar JSON
    output = {
        "meta": {
            "timestamp_utc":      now_utc.isoformat(),
            "timestamp_chile":    now_cl.isoformat(),
            "fuente":             "VipNet — DGA/MOP (vipnet.mop.gob.cl)",
            "aviso":              "Datos provisorios sujetos a revisión — DGA/MOP. "
                                  "Estaciones [proxy]: cobertura geográfica aproximada.",
            "fetch_ok":           ok,
            "n_estaciones_ok":    n_ok,
            "n_estaciones":       12,
            "n_raw_registros":    total_raw,
            "prox_actualizacion": (now_utc + timedelta(hours=1)).isoformat(),
        },
        "estaciones": results,
    }

    print(f"\n[3/3] Guardando → {OUTPUT}")
    os.makedirs("docs", exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  ✓ {os.path.getsize(OUTPUT):,} bytes · {n_ok}/12 con dato")
    return 0


if __name__ == "__main__":
    sys.exit(main())
