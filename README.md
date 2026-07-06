# SATH — DGA Bridge

Puente automático entre la red hidrométrica DGA (SNIA/MOP) y el dashboard
SATH. GitHub Actions extrae datos cada hora y los publica en GitHub Pages
como JSON público que el SATH lee directamente.

## Arquitectura

```
DGA DGASAT (snia.mop.gob.cl)
        ↓  cada 1h (GitHub Actions)
  fetch_dga.py   ←  DGA_USER / DGA_PASS (GitHub Secrets)
        ↓
  docs/dga_losrios.json
        ↓  GitHub Pages (HTTPS público)
  SATH v5 Dashboard
        ↓  TVC real + NR real
  Semáforo de alerta
```

## Setup — 5 pasos

### 1. Crear el repositorio en GitHub

```bash
# En tu máquina local
git clone https://github.com/TU_USUARIO/sath-dga-bridge
cd sath-dga-bridge
# Copiar todos estos archivos, luego:
git add -A && git commit -m "Initial SATH DGA Bridge"
git push
```

O más simple: crear el repo en github.com → "New repository" → nombre
`sath-dga-bridge` → Public → subir los archivos desde la web.

### 2. Activar GitHub Pages

En el repositorio → **Settings → Pages**:
- Source: **Deploy from a branch**
- Branch: `main`
- Folder: `/docs`
- Guardar

Tu URL pública será:
```
https://TU_USUARIO.github.io/sath-dga-bridge/dga_losrios.json
```

### 3. Agregar credenciales DGA como Secrets

En el repositorio → **Settings → Secrets and variables → Actions → New secret**:

| Secret name | Valor |
|---|---|
| `DGA_USER` | Tu usuario DGA Hidrolínea |
| `DGA_PASS` | Tu contraseña DGA Hidrolínea |

> Si aún no tienes cuenta DGA, créala en:
> https://snia.mop.gob.cl/dgasat/pages/dgasat_login/dgasat_login.htm
> O solicita acceso al DIRH: +56 2 2449 40 00 opción 4

### 4. Verificar primera ejecución

En → **Actions → SATH — DGA Data Bridge → Run workflow**

El workflow tarda ~2 minutos. Luego verifica:
- `docs/dga_losrios.json` actualizado con datos reales
- Status page: `https://TU_USUARIO.github.io/sath-dga-bridge/`

### 5. Conectar SATH al bridge

En `SATH_v5.html`, busca `DGA_BRIDGE_URL` y reemplaza con tu URL:

```javascript
const DGA_BRIDGE_URL =
  'https://TU_USUARIO.github.io/sath-dga-bridge/dga_losrios.json';
```

## Estructura del JSON de salida

```json
{
  "meta": {
    "timestamp_utc": "2026-07-06T12:00:00Z",
    "login_ok": true,
    "n_estaciones_ok": 10
  },
  "estaciones": {
    "antihue": {
      "codigo": "10122002",
      "nombre": "Rio Calle Calle En Antilhue",
      "cuenca": "Calle-Calle",
      "lat": -39.85,
      "lon": -73.10,
      "q_m3s": 342.5,
      "nivel_m": 1.234,
      "pp_mm": 12.4,
      "fecha_dato": "2026-07-06 11:00",
      "estado": "ok"
    }
  }
}
```

## Estaciones monitoreadas

| ID SATH       | Código DGA | Nombre                                   | Cuenca      |
|---------------|-----------|------------------------------------------|-------------|
| antihue       | 10122002  | Rio Calle Calle En Antilhue              | Calle-Calle |
| rinihue       | 10111001  | Rio San Pedro En Desague Lago Rinihue    | San Pedro   |
| mamalona      | 10113003  | Rio San Pedro En Pucono                  | San Pedro   |
| valdivia      | 10134001  | Rio Cruces En Rucaco                     | Cruces      |
| corral        | 10200001  | Meteorologica Corral                     | Costero     |
| lacpicada     | 10133000  | Rio Leufucade En Purulon                 | Cruces      |
| laslomas      | 10411002  | Rio Negro En Las Lomas                   | Bueno-sur   |
| tegualda      | 10351001  | Rio Toro En Tegualda                     | San Pedro   |
| panguipulli   | 10107003  | Canal Hueninca → Lago Calafquén          | Calle-Calle |
| pilmaiquen    | 10328001  | Rio Pilmaiquen En San Pablo              | Bueno-Ranco |
| launion       | 10313001  | Rio Llollelhue En La Union               | Bueno       |
| riobueno      | 10311001  | Rio Bueno En Bueno                       | Bueno       |

## Troubleshooting

**El workflow falla con error de login:**
- Verifica que `DGA_USER` y `DGA_PASS` estén bien escritos en los Secrets
- Prueba las credenciales manualmente en https://snia.mop.gob.cl/dgasat/

**Los datos muestran `q_m3s: null`:**
- El scraper navegó bien pero no encontró datos numéricos en la página
- La DGA puede haber cambiado el HTML de la interfaz
- Abrir un issue en el repo con el HTML que está retornando la página

**GitHub Pages no muestra el JSON:**
- Esperar 2-5 min después del primer push para que Pages se active
- Verificar Settings → Pages que apunta a `main` / `/docs`

## Licencia

Uso institucional interno. Datos provisorios © DGA/MOP Chile.

---
*Daniel Epprecht Valderrama · SATH · 2026*
