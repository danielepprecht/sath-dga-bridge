#!/usr/bin/env python3
"""SATH DGA Bridge v9 — VipNet API — mapeo honesto (sin caudal falso)

CAMBIO CRÍTICO v9 (2026-07-20):
VipNet (vipnet.mop.gob.cl / VHN "Visualizador Hidrométrico Nacional") es una
red METEOROLÓGICA (Precipitación, Temperatura, Embalse, Nieve, Humedad,
Viento). NO expone Caudal ni Nivel de río como variable, para ninguna
estación. El campo "value" que trae cada registro del endpoint
/v1/vipnet/estaciones/valor es un placeholder que en la práctica vale 0 para
TODAS las estaciones fluviométricas (se verificó en vivo para las 12
estaciones SATH, incluidas las que este script venía marcando "ok").

En v8, extract_value() caía de vuelta a ese campo "value" cuando no
encontraba parámetros anidados, así que el bridge llevaba semanas publicando
q_m3s=0.0 disfrazado de dato real para 9/12 estaciones. v9 elimina ese
fallback: si no hay un parámetro anidado real, la estación queda
"sin_telemetria" — sin inventar ceros.

La fuente real de caudal/nivel de DGA es DGASAT/Hidrolínea
(snia.mop.gob.cl/dgasat), que es el diseño original de este bridge (ver
README) y para la que ya existen los secrets DGA_USER/DGA_PASS. Verificado
en vivo (sesión autenticada manual): DGASAT SÍ tiene datos reales y
recientes para varias de estas estaciones (ej. 10134001 Río Cruces en
Rucaco). El bloqueo para automatizarlo por hora vía GitHub Actions es que el
login de DGASAT exige un token de Google reCAPTCHA generado interactivamente
en el navegador — no es algo que este script (requests, sin navegador) pueda
resolver, y no se debe intentar sortear una verificación anti-bot de forma
automatizada. Detalle y próximos pasos en README → "Limitación conocida".
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
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "es-ES,es;q=0.9",
}

# Mapeo de estaciones SATH → código DGA oficial.
# NOTA v9: los códigos "proxy" heredados de v8 (rinihue/mamalona/panguipulli/
# riobueno con códigos distintos al oficial) también carecían de caudal real
# en VipNet — se verificó que ESE endpoint no tiene caudal para ningún
# código, sea el oficial o el proxy. Se mantienen documentados por si en el
# futuro se conecta una fuente que sí sirva esos códigos, pero ya no se
# presentan como "ok" con datos falsos.
SATH_STATIONS = {
    "10200001": "corral",
    "10133000": "lacpicada",
    "10313001": "launion",
    "10328001": "pilmaiquen",
    "10111015": "rinihue",      # proxy VipNet — Lago Riñihue Estacion de Control
    "10327006": "riobueno",     # proxy VipNet — Escuela Rural Crucero (cuenca Río Bueno)
    "10307009": "panguipulli",  # proxy VipNet — Futrono Sector Las Quemas (cuenca Lago Ranco)
    "10122003": "pupunahue",    # Rio Calle Calle En Pupunahue
    "10304011": "mamalona",     # proxy VipNet — Fundo Sichahue (cuenca San Pedro/Calcurrupe)
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
    "pupunahue":   {"nombre":"Rio Calle Calle En Pupunahue", "cuenca":"Calle-Calle", "lat":-39.72,"lon":-72.47},
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


# ── Bounding boxes geográficos por región (lat/lon Chile WGS84) ──────────
REGION_BBOX = {
    15: {"s":-18.5,"n":-17.3,"w":-71.0,"e":-68.5},  # Arica y Parinacota
    1:  {"s":-20.5,"n":-18.5,"w":-70.2,"e":-68.0},  # Tarapacá
    2:  {"s":-26.5,"n":-20.5,"w":-70.5,"e":-65.0},  # Antofagasta
    3:  {"s":-29.1,"n":-26.5,"w":-72.0,"e":-67.0},  # Atacama
    4:  {"s":-32.3,"n":-29.0,"w":-72.0,"e":-69.5},  # Coquimbo
    5:  {"s":-33.8,"n":-32.0,"w":-72.0,"e":-69.8},  # Valparaíso
    13: {"s":-34.4,"n":-33.0,"w":-71.5,"e":-69.6},  # Metropolitana
    6:  {"s":-35.1,"n":-33.5,"w":-72.0,"e":-70.0},  # O'Higgins
    7:  {"s":-36.6,"n":-34.9,"w":-72.5,"e":-70.0},  # Maule
    16: {"s":-37.5,"n":-36.4,"w":-73.0,"e":-70.5},  # Ñuble
    8:  {"s":-38.6,"n":-36.4,"w":-73.5,"e":-70.5},  # Biobío
    9:  {"s":-39.5,"n":-37.4,"w":-73.6,"e":-70.8},  # Araucanía
    14: {"s":-40.5,"n":-39.4,"w":-73.7,"e":-71.5},  # Los Ríos
    10: {"s":-44.0,"n":-40.4,"w":-75.0,"e":-71.5},  # Los Lagos
    11: {"s":-49.0,"n":-43.9,"w":-75.6,"e":-70.0},  # Aysén
    12: {"s":-55.9,"n":-48.9,"w":-76.0,"e":-65.0},  # Magallanes
}

def classify_station_region(lat, lon):
    """Retorna el número de región según lat/lon. None si no aplica."""
    if lat is None or lon is None: return None
    try:
        lat, lon = float(lat), float(lon)
    except: return None
    for reg, bb in REGION_BBOX.items():
        if bb["s"] <= lat <= bb["n"] and bb["w"] <= lon <= bb["e"]:
            return reg
    return None

def build_stations_chile(all_raw_records):
    """Clasifica todas las estaciones VipNet por región y genera JSON."""
    stations_by_region = {reg: [] for reg in REGION_BBOX}
    seen_codes = set()
    for item in all_raw_records:
        if not isinstance(item, dict): continue
        lat = item.get("latitud") or item.get("lat")
        lon = item.get("longitud") or item.get("lon")
        cod = str(item.get("codigoEstacion") or item.get("codigo") or "").split("-")[0]
        nom = str(item.get("nombre") or cod).strip()
        if not cod or cod in seen_codes: continue
        reg = classify_station_region(lat, lon)
        if reg is None: continue
        seen_codes.add(cod)
        val_raw = item.get("value")
        try: val = round(float(val_raw), 3) if val_raw is not None else None
        except: val = None
        stations_by_region[reg].append({
            "cod": cod,
            "name": nom.title(),
            "lat": round(float(lat), 4),
            "lon": round(float(lon), 4),
            "q": val
        })
    # Sort each region by name
    for reg in stations_by_region:
        stations_by_region[reg].sort(key=lambda x: x["name"])
    return stations_by_region


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
    """Busca un valor de caudal/nivel REAL en parámetros anidados.

    v9: se eliminó el fallback al campo "value" de nivel superior — ese
    campo no representa una medición fluviométrica real en las respuestas
    de VipNet observadas (siempre 0 para las 12 estaciones SATH). Si no hay
    un parámetro anidado explícito, se retorna None en vez de inventar 0.
    """
    for nk in ("parametros","datos","valores","params","mediciones"):
        nested = item.get(nk)
        if not isinstance(nested, list): continue
        for p in nested:
            if not isinstance(p, dict): continue
            val = get_numeric(p,"value","valor","ultimo","ultimoValor")
            if val is not None:
                return val, get_text(p,"fecha","date","fechaHora"), get_text(p,"nombre","variable") or "—"
    fec = get_text(item,"fecha","date","fechaHora","ultimaFecha","fechaDato")
    var = get_text(item,"nombre","variable","nombreVariable") or "—"
    return None, fec, var


def main():
    now_utc = datetime.now(timezone.utc)
    now_cl  = now_utc.astimezone(timezone(timedelta(hours=-4)))
    print("="*65)
    print(f"SATH DGA Bridge v9 — {now_cl.strftime('%Y-%m-%d %H:%M')} CL")
    print("="*65)

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

    print(f"\n  Total registros: {total_raw} | SATH encontradas en índice VipNet: {len(all_records)}/12")
    print("  (indice != telemetria real: VipNet no expone caudal/nivel, ver cabecera del script)")

    # Generar stations_chile.json para el SATH nacional (mapa de precipitación/otros,
    # no reemplaza caudal — mismo alcance que v8)
    try:
        all_raw = list(all_records.values())
        stations_by_region = build_stations_chile(all_raw)
        total_stns = sum(len(v) for v in stations_by_region.values())
        with open("docs/stations_chile.json", "w", encoding="utf-8") as f:
            json.dump(stations_by_region, f, ensure_ascii=False)
        print(f"\n[1b/3] stations_chile.json: {total_stns} estaciones en {len([r for r,s in stations_by_region.items() if s])} regiones")
    except Exception as e:
        print(f"[WARN] stations_chile.json: {e}")

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
            "estado":     "ok" if val is not None else "sin_telemetria",
        }
        icon = "✓" if val is not None else "~"
        proxy_tag = " [proxy]" if es_proxy else ""
        print(f"  [{icon}] {stn_id:<12} Q={val} var={var[:25]}{proxy_tag}")

    # Estaciones que ni siquiera aparecen en el índice VipNet
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
            print(f"  [—] {stn_id:<12} sin telemetría en índice VipNet")

    n_ok = sum(1 for v in results.values() if v["estado"] == "ok")

    output = {
        "meta": {
            "timestamp_utc":      now_utc.isoformat(),
            "timestamp_chile":    now_cl.isoformat(),
            "fuente":             "VipNet — DGA/MOP (vipnet.mop.gob.cl)",
            "aviso":              "Datos provisorios sujetos a revisión — DGA/MOP. "
                                  "Estaciones [proxy]: cobertura geográfica aproximada.",
            "limitacion_conocida": (
                "VipNet (VHN) es una red meteorológica: no expone caudal ni nivel de río "
                "para ninguna estación, por lo que 'sin_telemetria' aquí refleja la "
                "realidad y no un error transitorio. La fuente autoritativa de caudal "
                "real es DGASAT/Hidrolínea (snia.mop.gob.cl/dgasat), cuyo login está "
                "protegido con reCAPTCHA y no puede resolverse desde este script sin "
                "intervención humana. Ver README → 'Limitación conocida' para el plan."
            ),
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
    print(f"  ✓ {os.path.getsize(OUTPUT):,} bytes · {n_ok}/12 con dato real")
    return 0


if __name__ == "__main__":
    sys.exit(main())
