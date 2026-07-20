# SATH — DGA Bridge

Puente automático entre la red hidrométrica DGA (SNIA/MOP) y el dashboard
SATH. GitHub Actions extrae datos cada hora y los publica en GitHub Pages
como JSON público que el SATH lee directamente.

## ✅ Actualización v10 (2026-07-20) — lectura real vía DGASAT

El bridge ahora puede publicar **caudal y nivel reales** de la Red
Hidrométrica DGA (DGASAT/Hidrolínea), no solo el índice meteorológico de
VipNet. Esto se logra sin automatizar el login (que exige reCAPTCHA):
un humano inicia sesión una vez en el navegador y copia la cookie de
sesión a un secret de GitHub. El script la reutiliza cada hora hasta
que expire; mientras tanto, sigue funcionando el respaldo honesto v9
(`sin_telemetria`) para lo que falte. Ver **"Cómo refrescar la cookie
de DGASAT"** más abajo para activarlo.

## ⚠️ Limitación conocida — origen (2026-07-20)

**Antes de v10, el bridge (`fetch_dga.py` v9) NO tenía caudal/nivel de
río real para ninguna de las 12 estaciones.** Diagnóstico completo:

1. El script consulta VipNet (`vipnet.mop.gob.cl`, el "VHN — Visualizador
   Hidrométrico Nacional"). VipNet es una red **meteorológica**
   (Precipitación, Temperatura, Embalse, Nieve, Humedad, Viento) — no
   expone Caudal ni Nivel de río como variable, para ninguna estación.
   Se verificó en vivo consultando el endpoint con `tipoEstacion` 0–6 y
   ventanas de hasta 24h: los 12 códigos DGA de este bridge nunca aparecen
   con un valor real; el campo `"value"` que sí trae cada registro es un
   placeholder que vale 0 para todas las estaciones fluviométricas.
2. Antes de v9, `extract_value()` caía de vuelta a ese campo `"value"`
   cuando no encontraba parámetros anidados, así que el bridge llevaba
   semanas publicando `q_m3s: 0.0` disfrazado de dato real para 9/12
   estaciones. v9 elimina ese fallback: ahora una estación solo se marca
   `"ok"` si hay un dato real, y el resto queda honestamente
   `"sin_telemetria"`.
3. La fuente real de caudal/nivel es **DGASAT/Hidrolínea**
   (`snia.mop.gob.cl/dgasat`), el diseño original de este bridge (ver
   diagrama abajo) — de hecho ya existen los secrets `DGA_USER`/`DGA_PASS`
   configurados, pero el script desde la migración a VipNet
   ("Migrate to VipNet API and remove DGA login") no los usa.
   Se verificó con una sesión autenticada manual que DGASAT **sí** tiene
   datos reales y recientes para varias de estas estaciones (ej. código
   `10134001`, Río Cruces en Rucaco: 2.27 m / 179 m³/s en la consulta de
   prueba).
4. **El bloqueo para automatizar DGASAT por hora vía GitHub Actions:** el
   login exige un token de Google reCAPTCHA generado interactivamente en
   el navegador. Un script sin navegador (`requests`) no puede resolverlo,
   y no corresponde construir algo que intente sortear una verificación
   anti-bot de forma automatizada.

**Próximos pasos recomendados** (requieren decisión/gestión humana, no
son ejecutables por un agente):
- Contactar al DIRH (+56 2 2449 40 00 opción 4) y solicitar explícitamente
  una **credencial de API institucional** para DGASAT/Hidrolínea que no
  dependa de reCAPTCHA (many organismos públicos chilenos ofrecen esto a
  usuarios institucionales tipo ONEMI).
- Alternativa manual: una persona inicia sesión en DGASAT periódicamente
  y copia los valores relevantes a mano (no escala para actualización
  horaria, pero es honesto).
- Mientras tanto, el bridge sigue corriendo cada hora y seguirá
  publicando `"sin_telemetria"` para las 12 estaciones — es preferible a
  publicar ceros falsos en un sistema de alerta temprana.

## Arquitectura

```
DGA DGASAT (snia.mop.gob.cl)  ← login con reCAPTCHA (manual, 1 vez)
        ↓  cookie de sesión → secret DGASAT_SESSION_COOKIE
        ↓  cada 1h (GitHub Actions)
  fetch_dga.py   ←  DGASAT_SESSION_COOKIE (real) + VipNet (respaldo/meteo)
        ↓  caudal/nivel real si la cookie está vigente, si no: sin_telemetria honesto
  docs/dga_losrios.json
        ↓  GitHub Pages (HTTPS público)
  SATH v5 Dashboard
        ↓  TVC real + NR real
  Semáforo de alerta
```

## Setup — 7 pasos

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
>
> **Nota:** estos secrets están configurados pero el script actual (v9)
> no los usa — ver "Limitación conocida" arriba. El login de DGASAT está
> protegido con reCAPTCHA y no es automatizable sin una credencial de API
> institucional.

### 4. (Opcional pero recomendado) Activar datos reales de DGASAT

Sin este paso, el bridge sigue funcionando pero publica
`sin_telemetria` para las 12 estaciones (comportamiento v9). Con este
paso, publica caudal y nivel reales mientras la cookie esté vigente.

**Cómo refrescar la cookie de DGASAT:**

1. Inicia sesión en <https://snia.mop.gob.cl/dgasat> con tu usuario y
   contraseña (resuelve el reCAPTCHA normalmente, en el navegador).
2. Con la sesión ya abierta, abre las **DevTools** del navegador
   (F12 o clic derecho → Inspeccionar) → pestaña **Network/Red**.
3. Navega a cualquier página dentro de DGASAT (por ejemplo, el reporte
   de alertas) para generar una petición.
4. Haz clic en esa petición → pestaña **Headers/Encabezados** → busca
   el encabezado de request **`Cookie`** → copia su valor completo
   (una cadena larga tipo `JSESSIONID=...; otracosa=...`).
5. En el repositorio → **Settings → Secrets and variables → Actions →
   New secret**:

   | Secret name | Valor |
   |---|---|
   | `DGASAT_SESSION_COOKIE` | El valor completo copiado en el paso 4 |

6. Guarda. La próxima ejecución del workflow (hasta 1h después, o
   manual vía Actions → Run workflow) ya intentará usarla.

**Importante — la cookie expira:** no se determinó su duración exacta
(se verificó viva por al menos ~5 minutos en pruebas manuales; podría
durar más). Cuando expire, el script simplemente vuelve al
comportamiento honesto v9 (`sin_telemetria`) para las estaciones sin
dato — no falla ni rompe el workflow. Para mantener datos reales de
forma sostenida, alguien debe repetir estos 6 pasos periódicamente
(ideal: una vez al día, o cuando `dgasat_estaciones_ok` en el JSON de
salida baje a 0). Esto es un mecanismo puente mientras se gestiona el
acceso institucional (ver solicitud DIRH incluida en este repo/entrega).

### 6. Verificar primera ejecución

En → **Actions → SATH — DGA Data Bridge → Run workflow**

El workflow tarda ~2 minutos. Luego verifica:
- `docs/dga_losrios.json` actualizado — revisa `meta.dgasat_estaciones_ok`:
  si es > 0, ya hay caudal/nivel real de DGASAT; si es 0, revisa que el
  secret `DGASAT_SESSION_COOKIE` esté vigente (paso 4)
- Status page: `https://TU_USUARIO.github.io/sath-dga-bridge/`

### 7. Conectar SATH al bridge

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
    "n_estaciones_ok": 0,
    "limitacion_conocida": "VipNet no expone caudal/nivel — ver README"
  },
  "estaciones": {
    "antihue": {
      "codigo": "10122002",
      "nombre": "Rio Calle Calle En Antilhue",
      "cuenca": "Calle-Calle",
      "lat": -39.85,
      "lon": -73.10,
      "q_m3s": null,
      "nivel_m": null,
      "pp_mm": null,
      "fecha_dato": null,
      "estado": "sin_telemetria"
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
- El script v9 no hace login a DGASAT (ver "Limitación conocida"), así
  que este error ya no debería ocurrir salvo que se reintroduzca ese
  flujo. Si aparece, revisar si alguien modificó `fetch_dga.py` para
  volver a intentar login.

**Los datos muestran `q_m3s: null` / `estado: sin_telemetria`:**
- Es el comportamiento esperado hoy para las 12 estaciones — no es un
  error transitorio, es la limitación documentada arriba. No reintentar
  "arreglarlo" agregando de vuelta un fallback a datos de VipNet: ese
  campo no es caudal real (confirmado).

**GitHub Pages no muestra el JSON:**
- Esperar 2-5 min después del primer push para que Pages se active
- Verificar Settings → Pages que apunta a `main` / `/docs`

## Licencia

Uso institucional interno. Datos provisorios © DGA/MOP Chile.

---
*Daniel Epprecht Valderrama · SATH · 2026*
