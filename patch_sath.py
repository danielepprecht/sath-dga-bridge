#!/usr/bin/env python3
"""
patch_sath.py — SATH Chile Nacional
Expande el SATH para cubrir las 16 regiones de Chile con calibración
específica por zona hidrológica. Datos DGA nacionales 330,000+ obs.
"""
import os, sys, re
from collections import Counter

SATH = "docs/SATH_v5.html"

REGION_CAL_JS = """
// ═══════════════════════════════════════════════════════════════════════
// REGION_CAL — Calibración por zona hidrológica · DGA Chile 2025
// Fuente: 330,000+ obs · 778 estaciones · 1960-2025
// ═══════════════════════════════════════════════════════════════════════
const REGION_CAL = {
  aluvial: {
    nombre:'Zona Aluvial — Norte Grande', color:'#dc2626', colorLight:'#fee2e2',
    alerta:'RIESGO DE ALUVIÓN', tipoEvento:'aluvion', dominante:'APC',
    tvc:{p:0.012,a:0.044,x:0.137,p99:1.279},
    ifa:{p:5,a:10,x:25}, sat:{p:10,a:20,x:40}, satMax:1.02,
    lagH:2, kRel:0.85, apcWeight:0.50, regiones:[1,2,15],
    desc:'Aluviones súbitos. Respuesta 1-4h. Riesgo en quebradas.'
  },
  semiarido: {
    nombre:'Zona Semiárida — Norte Chico', color:'#ea580c', colorLight:'#ffedd5',
    alerta:'RIESGO DE CRECIDA', tipoEvento:'crecida_aluvion', dominante:'APC+IFA',
    tvc:{p:0.050,a:0.160,x:0.450,p99:2.727},
    ifa:{p:10,a:25,x:50}, sat:{p:20,a:45,x:80}, satMax:1.05,
    lagH:5, kRel:0.75, apcWeight:0.35, regiones:[3,4],
    desc:'Ríos estacionales. Crecidas rápidas tras lluvias concentradas.'
  },
  mediterraneo: {
    nombre:'Zona Mediterránea — Zona Central', color:'#d97706', colorLight:'#fef3c7',
    alerta:'RIESGO DE DESBORDE', tipoEvento:'desborde', dominante:'IFA',
    tvc:{p:0.314,a:1.600,x:6.500,p99:87.068},
    ifa:{p:20,a:50,x:100}, sat:{p:60,a:130,x:210}, satMax:1.15,
    lagH:12, kRel:0.65, apcWeight:0.20, regiones:[5,6,7,13],
    desc:'Invierno lluvioso, verano seco. Crecidas en ríos andinos.'
  },
  mixto: {
    nombre:'Zona Mixta Pluvio-Nival — Centro-Sur', color:'#16a34a', colorLight:'#dcfce7',
    alerta:'RIESGO DE DESBORDE DE RÍO', tipoEvento:'desborde', dominante:'TVC+IFA',
    tvc:{p:0.520,a:3.300,x:15.100,p99:158.0},
    ifa:{p:35,a:70,x:110}, sat:{p:90,a:175,x:285}, satMax:1.20,
    lagH:20, kRel:0.70, apcWeight:0.15, regiones:[8,9,16],
    desc:'Ríos Biobío, Imperial, Itata. Componente nival en Andes.'
  },
  pluvial: {
    nombre:'Zona Pluvial — Sur', color:'#0891b2', colorLight:'#e0f2fe',
    alerta:'ALERTA POR DESBORDE DE RÍO', tipoEvento:'desborde', dominante:'TVC+IFA+SAT',
    tvc:{p:0.40,a:1.06,x:3.81,p99:8.63},
    ifa:{p:51.8,a:81.7,x:115.8}, sat:{p:100,a:200,x:350}, satMax:1.25,
    lagH:24, kRel:0.60, apcWeight:0.10, regiones:[14,10],
    desc:'Cuencas lacustres. Saturación suelo relevante. Calibrado CR2 1913-2020.'
  },
  pluvial_nival: {
    nombre:'Zona Austral Pluvio-Nival', color:'#7c3aed', colorLight:'#ede9fe',
    alerta:'ALERTA POR DESBORDE DE RÍO', tipoEvento:'desborde', dominante:'TVC+IFA+SAT',
    tvc:{p:0.917,a:4.800,x:18.600,p99:165.65},
    ifa:{p:60,a:100,x:150}, sat:{p:120,a:250,x:400}, satMax:1.25,
    lagH:36, kRel:0.55, apcWeight:0.10, regiones:[11,12],
    desc:'Baker, Pascua, Palena. Componente glacial. Respuesta lenta.'
  }
};
const REGION_ZONA={1:'aluvial',2:'aluvial',15:'aluvial',3:'semiarido',4:'semiarido',
  5:'mediterraneo',6:'mediterraneo',7:'mediterraneo',13:'mediterraneo',
  8:'mixto',9:'mixto',16:'mixto',14:'pluvial',10:'pluvial',
  11:'pluvial_nival',12:'pluvial_nival'};
const REGIONES_CHILE=[
  {num:15,nom:'XV \u2014 Arica y Parinacota',zona:'aluvial'},
  {num:1, nom:'I \u2014 Tarapac\u00e1',zona:'aluvial'},
  {num:2, nom:'II \u2014 Antofagasta',zona:'aluvial'},
  {num:3, nom:'III \u2014 Atacama',zona:'semiarido'},
  {num:4, nom:'IV \u2014 Coquimbo',zona:'semiarido'},
  {num:5, nom:'V \u2014 Valpara\u00edso',zona:'mediterraneo'},
  {num:13,nom:'RM \u2014 Metropolitana',zona:'mediterraneo'},
  {num:6, nom:'VI \u2014 O\u2019Higgins',zona:'mediterraneo'},
  {num:7, nom:'VII \u2014 Maule',zona:'mediterraneo'},
  {num:16,nom:'XVI \u2014 \u00d1uble',zona:'mixto'},
  {num:8, nom:'VIII \u2014 Biob\u00edo',zona:'mixto'},
  {num:9, nom:'IX \u2014 Araucan\u00eda',zona:'mixto'},
  {num:14,nom:'XIV \u2014 Los R\u00edos',zona:'pluvial'},
  {num:10,nom:'X \u2014 Los Lagos',zona:'pluvial'},
  {num:11,nom:'XI \u2014 Ays\u00e9n',zona:'pluvial_nival'},
  {num:12,nom:'XII \u2014 Magallanes',zona:'pluvial_nival'},
];
var activeRegion=14, activeZone='pluvial';
function getZoneCal(){return REGION_CAL[activeZone]||REGION_CAL.pluvial;}
"""

REGION_FNS_JS = """
// ═══════════════════════════════════════════════════════════════════════
// FUNCIONES NACIONALES SATH CHILE
// ═══════════════════════════════════════════════════════════════════════

// scoreNR adaptado a la zona activa
function scoreNR(tvc,ifa,apc){
  const cal=getZoneCal();
  const tp=cal.tvc.p,ta=cal.tvc.a,tx=cal.tvc.x;
  const ip=cal.ifa.p,ia=cal.ifa.a,ix=cal.ifa.x;
  const aw=cal.apcWeight||0.10;
  var tvcPos=Math.max(0,tvc);
  var ts=tvcPos>=tx?Math.min(100,90+(tvcPos-tx)/tx*15):tvcPos>=ta?80+(tvcPos-ta)/(tx-ta)*10:tvcPos>=tp?70+(tvcPos-tp)/(ta-tp)*10:tvcPos/tp*65;
  var is_=ifa>=ix?Math.min(100,90+(ifa-ix)/ix*10):ifa>=ia?80+(ifa-ia)/(ix-ia)*10:ifa>=ip?70+(ifa-ip)/(ia-ip)*10:ifa/ip*65;
  var apcPos=Math.max(0,apc||0);
  var as_=Math.min(8+Math.round(aw*42),apcPos/(cal.tvc.p*0.5)*8*(1+aw*2));
  as_=Math.min(as_,8+Math.round(aw*42));
  var nr=Math.max(ts,is_);
  if(ts>=70&&is_>=70)nr=Math.min(100,nr+0.1*Math.min(ts,is_));
  nr=Math.min(100,nr+as_);
  return{nr:Math.min(100,Math.round(nr)),ts:Math.round(ts),is_:Math.round(is_),as_:Math.round(as_)};
}

// satFactor adaptado a la zona
function satFactor(ifa168){
  const cal=getZoneCal();
  const sm=cal.satMax||1.25;
  const sp=cal.sat.p,sa=cal.sat.a,sx=cal.sat.x;
  if(!ifa168||ifa168<sp)return 1.0;
  if(ifa168<sa)return 1.0+(ifa168-sp)/(sa-sp)*(sm-1)*0.4;
  if(ifa168<sx)return 1.0+(ifa168-sp)/(sx-sp)*(sm-1)*0.8;
  return sm;
}

// Texto alerta según zona
function alertaTxt(nr){
  const cal=getZoneCal();
  const ev=cal.tipoEvento||'desborde';
  if(nr>=90){
    if(ev==='aluvion')return '\U0001F534 ALARMA DE ALUVIÓN';
    return '\U0001F534 ALARMA DE RIESGO POR DESBORDE DE RÍO';
  }
  if(nr>=80){
    if(ev==='aluvion')return '\U0001F6A8 ALERTA DE ALUVIÓN';
    if(ev==='crecida_aluvion')return '\U0001F6A8 ALERTA DE CRECIDA';
    return '\U0001F6A8 ALERTA POR DESBORDE DE RÍO';
  }
  if(nr>=70){
    if(ev==='aluvion')return '\u26A0 PRECAUCIÓN ALUVIÓN';
    return '\u26A0 ESTADO DE PRECAUCIÓN';
  }
  return '';
}

// Carga dinámica de estaciones VipNet por región
var regionStations={};
async function loadRegionStations(regNum){
  const now=new Date();
  const pad=n=>String(n).padStart(2,'0');
  const payload={tipoEstacion:0,mapStatistic:4,currentTabIndex:0,
    fetchHour:now.getHours(),
    fetchDay:now.getFullYear()+'-'+pad(now.getMonth()+1)+'-'+pad(now.getDate()),
    hoursRange:3};
  try{
    const r=await fetch('https://vipnet.mop.gob.cl/v1/vipnet/estaciones/valor',
      {method:'POST',headers:{'Content-Type':'application/json',
       'Origin':'https://vipnet.mop.gob.cl'},body:JSON.stringify(payload)});
    if(!r.ok)return null;
    const data=await r.json();
    const stns=data.filter(function(d){
      return typeof d==='object'&&d!==null&&
        (String(d.region)===String(regNum)||String(d.regionEstacion)===String(regNum));
    }).map(function(d){
      const cod=String(d.codigoEstacion||'').split('-')[0];
      return {
        id:'r'+regNum+'_'+cod,
        cod:cod,
        name:toTitleCase(String(d.nombre||cod)),
        lat:d.latitud,lon:d.longitud,
        cuenca:'Región '+regNum,
        tipo:'Fluviométrica',
        access:'dga',
        value:d.value
      };
    }).filter(function(s){return s.lat&&s.lon&&s.cod;});
    regionStations[regNum]=stns;
    return stns;
  }catch(e){return null;}
}

function toTitleCase(s){
  return s.toLowerCase().replace(/(?:^|\\s|-)\\S/g,function(c){return c.toUpperCase();});
}

// Cambiar región activa
async function setRegion(regNum){
  activeRegion=parseInt(regNum);
  activeZone=REGION_ZONA[activeRegion]||'pluvial';
  const cal=getZoneCal();
  // Actualizar badge de zona
  const zb=document.getElementById('zone-badge');
  if(zb){
    zb.textContent=cal.nombre;
    zb.style.background=cal.colorLight;
    zb.style.color=cal.color;
    zb.style.border='1px solid '+cal.color;
  }
  // Actualizar descripción zona
  const zd=document.getElementById('zone-desc');
  if(zd)zd.textContent=cal.desc;
  // Cargar estaciones VipNet de la región
  const loadingEl=document.getElementById('region-loading');
  if(loadingEl)loadingEl.style.display='flex';
  let stns=regionStations[activeRegion];
  if(!stns){stns=await loadRegionStations(activeRegion);}
  if(loadingEl)loadingEl.style.display='none';
  // Reconstruir dropdown de estaciones
  buildRegionStationSel(stns||[]);
  // Si hay estaciones, seleccionar la primera
  if(stns&&stns.length>0){
    setRegionStation(stns[0]);
  }
}

function buildRegionStationSel(stns){
  const sel=document.getElementById('sel-region-stn');
  if(!sel)return;
  sel.innerHTML='';
  if(!stns||stns.length===0){
    const opt=document.createElement('option');
    opt.textContent='Sin estaciones con telemetría activa';
    sel.appendChild(opt);
    return;
  }
  stns.forEach(function(s){
    const opt=document.createElement('option');
    opt.value=s.id;
    opt.textContent=s.name+(s.value!=null?' — Q:'+Number(s.value).toFixed(2)+' m³/s':'');
    opt.dataset.cod=s.cod;
    sel.appendChild(opt);
  });
}

function setRegionStation(stn){
  // Actualizar coordenadas activas para Open-Meteo
  if(!stn||!stn.lat||!stn.lon)return;
  // Crear entrada temporal en STNS para que fetchOM funcione
  const tempId='_region_'+stn.cod;
  STNS[tempId]={name:stn.name,lat:stn.lat,lon:stn.lon,
    cuenca:stn.cuenca,tipo:stn.tipo,access:'dga',cod:stn.cod};
  activeStn=tempId;
  fetchOM(tempId).then(function(){
    rebuildALLFromRealData(tempId);
    updSATHFromRealData(tempId);
    renderFcstSelected(tempId);
    updRealIFA();
  });
}
"""

REGION_UI_HTML = """
    <!-- SATH Chile: selector de región y zona -->
    <div id="region-panel" style="background:#0f172a;border-bottom:1px solid #1e3a5f;padding:8px 16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
      <span style="font-size:10px;color:#64748b;font-weight:700;letter-spacing:1px">REGIÓN</span>
      <select id="sel-region" onchange="setRegion(this.value)"
        style="background:#1e293b;color:#e2e8f0;border:1px solid #334155;border-radius:6px;
               padding:4px 10px;font-size:12px;cursor:pointer;min-width:220px">
        <optgroup label="── Zona Aluvial ──">
          <option value="15">XV — Arica y Parinacota</option>
          <option value="1">I — Tarapacá</option>
          <option value="2">II — Antofagasta</option>
        </optgroup>
        <optgroup label="── Zona Semiárida ──">
          <option value="3">III — Atacama</option>
          <option value="4">IV — Coquimbo</option>
        </optgroup>
        <optgroup label="── Zona Mediterránea ──">
          <option value="5">V — Valparaíso</option>
          <option value="13">RM — Metropolitana</option>
          <option value="6">VI — O'Higgins</option>
          <option value="7">VII — Maule</option>
        </optgroup>
        <optgroup label="── Zona Mixta Pluvio-Nival ──">
          <option value="16">XVI — Ñuble</option>
          <option value="8">VIII — Biobío</option>
          <option value="9">IX — Araucanía</option>
        </optgroup>
        <optgroup label="── Zona Pluvial ──">
          <option value="14" selected>XIV — Los Ríos</option>
          <option value="10">X — Los Lagos</option>
        </optgroup>
        <optgroup label="── Zona Austral ──">
          <option value="11">XI — Aysén</option>
          <option value="12">XII — Magallanes</option>
        </optgroup>
      </select>
      <span id="zone-badge" style="font-size:10px;font-weight:700;padding:3px 10px;
        border-radius:12px;border:1px solid #0891b2;background:#e0f2fe;color:#0891b2">
        Zona Pluvial — Sur</span>
      <span id="zone-desc" style="font-size:9px;color:#64748b;max-width:340px;
        display:none" class="md-show">
        Cuencas lacustres. Saturación suelo relevante.</span>
      <span id="region-loading" style="display:none;font-size:10px;color:#60a5fa;
        align-items:center;gap:6px">
        <span style="animation:spin 1s linear infinite;display:inline-block">⟳</span>
        Cargando estaciones VipNet...</span>
    </div>
    <!-- Selector de estación por región (se llena dinámicamente) -->
    <div id="region-stn-panel" style="background:#0a1628;padding:6px 16px;
      display:none;border-bottom:1px solid #1e3a5f">
      <select id="sel-region-stn" onchange="onRegionStnChange(this)"
        style="background:#1e293b;color:#e2e8f0;border:1px solid #334155;
               border-radius:6px;padding:4px 10px;font-size:11px;width:100%;max-width:500px">
        <option>Selecciona una región primero</option>
      </select>
    </div>"""

REGION_CHANGE_JS = """
function onRegionStnChange(sel){
  const regNum=parseInt(document.getElementById('sel-region').value);
  const stns=regionStations[regNum]||[];
  const stn=stns.find(function(s){return s.id===sel.value;});
  if(stn)setRegionStation(stn);
}

// Al cambiar a una región distinta de XIV, mostrar panel estación regional
document.getElementById('sel-region').addEventListener('change',function(){
  const regNum=parseInt(this.value);
  const regStnPanel=document.getElementById('region-stn-panel');
  if(regNum!==14&&regNum!==10){
    if(regStnPanel)regStnPanel.style.display='block';
  } else {
    if(regStnPanel)regStnPanel.style.display='none';
  }
});
"""

def patch(html):
    match = re.search(r'(<script>)(.*?)(</script>)', html, re.DOTALL)
    if not match:
        return html, []
    js = match.group(2)
    orig_js = js
    log = []

    # ── 1. Inyectar REGION_CAL antes de STNS ─────────────────────────────
    if 'REGION_CAL' not in js and 'const STNS' in js:
        js = REGION_CAL_JS + '\n' + js
        log.append("REGION_CAL: calibración 6 zonas hidrológicas")

    # ── 2. Inyectar funciones nacionales después de satFactor ─────────────
    if 'function loadRegionStations(' not in js:
        target = '\nfunction buildRealData('
        if target in js:
            js = js.replace(target, REGION_FNS_JS + target, 1)
            log.append("Funciones SATH Chile: scoreNR adaptado + carga dinámica VipNet")

    # ── 3. Agregar onchange handler al final del script ───────────────────
    if 'onRegionStnChange' not in js:
        js = js + '\n' + REGION_CHANGE_JS
        log.append("Handler cambio de estación regional")

    # ── 4. Inyectar UI del selector de región en el HTML ─────────────────
    if 'sel-region' not in html:
        # Insert before the station tabs
        target_html = '<div id="stn-tabs"'
        if target_html in html:
            html = html.replace(target_html,
                                REGION_UI_HTML + '\n    <div id="stn-tabs"', 1)
            log.append("UI: selector región + badge zona")

    # ── 5. Nombres oficiales DGA en STNS ──────────────────────────────────
    if 'Leufucade' not in js and 'const STNS' in js:
        old_stns = js[js.find('const STNS'):js.find('};', js.find('const STNS'))+2]
        new_stns = """const STNS = {
  antihue:    {name:'Río Calle-Calle en Antilhue',    cod:'10122002',lat:-39.85,lon:-73.10,cuenca:'Calle-Calle', tipo:'Fluviométrica',access:'dga'},
  rinihue:    {name:'Río San Pedro en Lago Riñihue',  cod:'10111001',lat:-39.79,lon:-72.43,cuenca:'San Pedro',   tipo:'Fluviométrica',access:'dga'},
  mamalona:   {name:'Río San Pedro en Pucono',        cod:'10113003',lat:-39.58,lon:-72.18,cuenca:'San Pedro',   tipo:'Fluviométrica',access:'dga'},
  valdivia:   {name:'Río Cruces en Rucaco',           cod:'10134001',lat:-39.64,lon:-73.09,cuenca:'Cruces',      tipo:'Fluviométrica',access:'dga'},
  corral:     {name:'Est. Meteorológica Corral',      cod:'10200001',lat:-39.88,lon:-73.43,cuenca:'Costero',     tipo:'Meteorológica',access:'dga'},
  lacpicada:  {name:'Río Leufucade en Purulón',       cod:'10133000',lat:-39.82,lon:-73.27,cuenca:'Cruces',      tipo:'Fluviométrica',access:'dga'},
  laslomas:   {name:'Río Negro en Las Lomas',         cod:'10411002',lat:-39.94,lon:-73.02,cuenca:'Bueno sur',   tipo:'Fluviométrica',access:'dga'},
  tegualda:   {name:'Río Toro en Tegualda',           cod:'10351001',lat:-40.17,lon:-72.62,cuenca:'San Pedro',   tipo:'Fluviométrica',access:'dga'},
  panguipulli:{name:'Canal Hueninca - Lago Calafquén',cod:'10107003',lat:-39.64,lon:-72.33,cuenca:'Calle-Calle',tipo:'Fluviométrica',access:'dga'},
  pupunahue:  {name:'Río Calle-Calle en Pupunahue',  cod:'10122003',lat:-39.72,lon:-72.47,cuenca:'Calle-Calle',tipo:'Fluviométrica',access:'dga'},
  pilmaiquen: {name:'Río Pilmaiquén en San Pablo',    cod:'10328001',lat:-40.18,lon:-72.37,cuenca:'Bueno-Ranco', tipo:'Fluviométrica',access:'dga'},
  launion:    {name:'Río Llollelhue en La Unión',     cod:'10313001',lat:-40.29,lon:-73.09,cuenca:'Bueno',       tipo:'Fluviométrica',access:'dga'},
  riobueno:   {name:'Río Bueno en Bueno',             cod:'10311001',lat:-40.69,lon:-72.97,cuenca:'Bueno',       tipo:'Fluviométrica',access:'dga'},
};"""
        if old_stns and old_stns in js:
            js = js.replace(old_stns, new_stns, 1)
            log.append("STNS: nombres DGA oficiales + Pupunahue (13 estaciones)")

    # ── 6. Dropdown sel-stn nombres DGA ──────────────────────────────────
    dropdown_replacements = [
        ('"antihue">Antihue (R. Calle-Calle)',       '"antihue">Río Calle-Calle en Antilhue'),
        ('"rinihue">L. Riñihue (DGA)',               '"rinihue">Río San Pedro en Lago Riñihue'),
        ('"mamalona">Mamalona (Panguipulli)',         '"mamalona">Río San Pedro en Pucono'),
        ('"valdivia">Valdivia (DMC)',                 '"valdivia">Río Cruces en Rucaco'),
        ('"corral">Corral (ESSAL/INIA)',              '"corral">Est. Meteorológica Corral'),
        ('"lacpicada">R. Cruces — La Picada',        '"lacpicada">Río Leufucade en Purulón'),
        ('"laslomas">Las Lomas (Máfil)',              '"laslomas">Río Negro en Las Lomas'),
        ('"tegualda">Tegualda (R. San Pedro)',        '"tegualda">Río Toro en Tegualda'),
        ('"panguipulli">Panguipulli (DMC/INIA)',     '"panguipulli">Canal Hueninca - Lago Calafquén'),
        ('"pilmaiquen">R. Pilmaiquén — Riñinahue',  '"pilmaiquen">Río Pilmaiquén en San Pablo'),
        ('"launion">La Unión (INIA)',                 '"launion">Río Llollelhue en La Unión'),
        ('"riobueno">Río Bueno (DGA)',               '"riobueno">Río Bueno en Bueno'),
    ]
    changed_drop = False
    for old_r, new_r in dropdown_replacements:
        if old_r in html:
            html = html.replace(old_r, new_r, 1)
            changed_drop = True
    if changed_drop:
        log.append("Dropdown sel-stn: nombres oficiales DGA")

    # Agregar Pupunahue al dropdown si no existe
    if 'value="pupunahue"' not in html:
        old_opt = '<option value="panguipulli">'
        new_opt = ('<option value="pupunahue">Río Calle-Calle en Pupunahue</option>\n'
                   '        <option value="panguipulli">')
        if old_opt in html:
            html = html.replace(old_opt, new_opt, 1)
            log.append("Dropdown: Pupunahue agregada")

    # ── 7. NR unificado ──────────────────────────────────────────────────
    if 'd[j].sf=' not in js:
        for old_nr, new_nr in [
            ("""  for(var j=0;j<d.length;j++){
    var sc=scoreNR(Math.max(0,d[j].tvc),d[j].ifa,d[j].apc);
    d[j].irc=+(sc.nr/100).toFixed(3);
  }
  return d;
}""",
            """  var _ifa168=(typeof fcstData!=='undefined'&&fcstData[id])?fcstData[id].realIFA168||0:0;
  var _sf=typeof satFactor==='function'?satFactor(_ifa168):1;
  for(var j=0;j<d.length;j++){
    var sc=scoreNR(Math.max(0,d[j].tvc),d[j].ifa,d[j].apc);
    d[j].irc=+Math.min(1,sc.nr*_sf/100).toFixed(3);
    d[j].sf=+_sf.toFixed(3);
    d[j].ifa168=+_ifa168.toFixed(0);
  }
  return d;
}""")
        ]:
            if old_nr in js:
                js = js.replace(old_nr, new_nr, 1)
                log.append("NR unificado con satFactor")
                break

    # ── 8. updSATHFromRealData sin sobreescribir NR ───────────────────────
    if 'var nr=rn.nrOper' in js:
        idx = js.find('function updSATHFromRealData(')
        end = js.find('\nfunction ', idx+20)
        new_fn = """function updSATHFromRealData(id){
  var rn=computeRealNR(id);if(!rn)return;
  if(rn.tvcReal>0){
    var elT=document.getElementById('v-tvc');
    if(elT)elT.textContent=rn.tvcReal.toFixed(2);
    var elAT=document.getElementById('a-tvc');
    if(elAT&&typeof tvcAct==='function')elAT.textContent=tvcAct(rn.tvcReal);
  }
  var i168=rn.realIFA168||0;
  var sfP=rn.satFactor?Math.round((rn.satFactor-1)*100):0;
  var lbl=i168>350?'Saturado':i168>200?'Muy húmedo':i168>100?'Húmedo':'Normal';
  var eA=document.getElementById('a-ifa');
  if(eA&&typeof ifaAct==='function')
    eA.innerHTML=ifaAct(rn.realIFA)+
      '<br><small style="color:#7c3aed">IFA 7d: '+Math.round(i168)+'mm | '+lbl+
      (sfP>0?' | +'+sfP+'% NR':'')+
      '</small>';
}"""
        if idx >= 0 and end > idx:
            js = js[:idx] + new_fn + js[end:]
            log.append("updSATHFromRealData: no sobreescribe NR")

    # ── 9. satFactor en tarjeta NR ────────────────────────────────────────
    if 'sat. IFA7d=' not in js:
        old_sf = "  updSATHSemaphore(nr);\n  document.getElementById('tr-tvc')"
        new_sf = (
            "  updSATHSemaphore(nr);\n"
            "  if(cur.sf&&cur.sf>1.01){\n"
            "    const elNRa=document.getElementById('a-irc');\n"
            "    if(elNRa){const sp=Math.round((cur.sf-1)*100);\n"
            "      elNRa.textContent=ircAct(cur.irc)+' (+'+sp+'% sat. IFA7d='+cur.ifa168+'mm)';}\n"
            "  }\n"
            "  document.getElementById('tr-tvc')"
        )
        if old_sf in js:
            js = js.replace(old_sf, new_sf, 1)
            log.append("satFactor visible en tarjeta NR")

    # ── 10. Verificar balance JS ──────────────────────────────────────────
    op = js.count('{'); cl = js.count('}')
    if op != cl:
        print(f"  ADVERTENCIA JS {{ {op} }} {cl} diff={op-cl}")

    if js != orig_js:
        html = html[:match.start(2)] + js + html[match.end(2):]

    return html, log

def main():
    if not os.path.exists(SATH):
        print(f"AVISO: {SATH} no encontrado — omitiendo"); return 0
    with open(SATH, encoding='utf-8') as f:
        html = f.read()
    print(f"Archivo: {len(html):,} bytes")
    new_html, log = patch(html)
    if new_html != html:
        with open(SATH, 'w', encoding='utf-8') as f:
            f.write(new_html)
        print(f"Guardado: {len(new_html):,} bytes")
        for l in log: print(f"  [+] {l}")
    else:
        print("Sin cambios")
    return 0

if __name__ == '__main__':
    sys.exit(main())
