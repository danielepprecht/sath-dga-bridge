#!/usr/bin/env python3
"""patch_sath.py — Aplica y corrige actualizaciones SATH_v5.html"""
import os, sys

SATH = "docs/SATH_v5.html"

def patch(html):
    orig = html
    log = []

    # ── FIX CRÍTICO: eliminar líneas con 'id' no definido en fetchAllOM ──
    # El parche anterior inyectó rebuildALLFromRealData(id) dentro de
    # fetchAllOM() donde 'id' no está definido → ReferenceError → todo rompe
    BAD1 = ("  updRealIFA();\n"
            "  rebuildALLFromRealData(id);\n"
            "  updSATHFromRealData(id);\n"
            "  fetchFloodForecast(activeStn);")
    OK1  = ("  updRealIFA();\n"
            "  fetchFloodForecast(activeStn);")
    if BAD1 in html:
        html = html.replace(BAD1, OK1, 1)
        log.append("FIX CRÍTICO: eliminadas líneas 'id' no definido en fetchAllOM")

    # Variante 2 del mismo bug
    BAD2 = ("  rebuildALLFromRealData(id);\n"
            "  updSATHFromRealData(id);\n"
            "  fetchFloodForecast(activeStn);")
    OK2  = "  fetchFloodForecast(activeStn);"
    if BAD2 in html:
        html = html.replace(BAD2, OK2, 1)
        log.append("FIX CRÍTICO v2: eliminadas líneas 'id' no definido")

    # ── simH=72 por defecto ──────────────────────────────────────────────
    if "simH=0,paused=false" in html:
        html = html.replace("simH=0,paused=false","simH=72,paused=true",1)
        log.append("simH=72")

    # ── Key migration Windy/Claude ───────────────────────────────────────
    for old_key in [
        "windyKey=sessionStorage.getItem('cogrid_windy_key')||'';",
        "windyKey=sessionStorage.getItem('equipo de alerta_windy_key')||'';"
    ]:
        if old_key in html and "Migracion automatica" not in html:
            migration = (old_key + "\n"
                "['equipo de alerta','sath','COGRID','senapred'].forEach(function(p){\n"
                "  var ow=sessionStorage.getItem(p+'_windy_key');\n"
                "  if(ow&&!windyKey){windyKey=ow;}\n"
                "  var oc=sessionStorage.getItem(p+'_claude_key');\n"
                "  if(oc&&!claudeKey){claudeKey=oc;}\n"
                "});\n// Migracion automatica")
            html = html.replace(old_key, migration, 1)
            log.append("Key migration Windy/Claude")
            break

    # ── NR real: scoreNR + buildRealData + rebuildALLFromRealData ────────
    NR_REAL = """
// === NR REAL + buildRealData desde Open-Meteo ERA5 ===
const NR_CAL={tvc:{p:0.40,a:1.06,x:3.81},ifa:{p:51.8,a:81.7,x:115.8}};
const _prevQ={};
function scoreNR(tvc,ifa){
  var tp=NR_CAL.tvc.p,ta=NR_CAL.tvc.a,tx=NR_CAL.tvc.x;
  var ip=NR_CAL.ifa.p,ia=NR_CAL.ifa.a,ix=NR_CAL.ifa.x;
  var ts=tvc>=tx?Math.min(100,90+(tvc-tx)/tx*15):tvc>=ta?80+(tvc-ta)/(tx-ta)*10:tvc>=tp?70+(tvc-tp)/(ta-tp)*10:tvc/tp*65;
  var is_=ifa>=ix?Math.min(100,90+(ifa-ix)/ix*10):ifa>=ia?80+(ifa-ia)/(ix-ia)*10:ifa>=ip?70+(ifa-ip)/(ia-ip)*10:ifa/ip*65;
  var nr=Math.max(ts,is_);
  if(ts>=70&&is_>=70)nr=Math.min(100,nr+0.1*Math.min(ts,is_));
  return{nr:Math.min(100,Math.round(nr)),ts:Math.round(ts),is_:Math.round(is_)};
}
function buildRealData(id){
  var fd=fcstData[id];
  if(!fd||!fd.ok||!fd.hourlyPP||fd.hourlyPP.length<73)return null;
  var hrPP=fd.hourlyPP;
  var curQ=(typeof dgaData!=='undefined'&&dgaData&&dgaData.estaciones&&dgaData.estaciones[id])?dgaData.estaciones[id].q_m3s||0:0;
  var d=[];
  for(var h=0;h<=72;h++){
    var pp=Math.max(0,+(hrPP[h]||0));
    d.push({h:h,pp:+pp.toFixed(1),q:+curQ.toFixed(1)});
  }
  for(var i=0;i<d.length;i++){
    d[i].dpp=i===0?0:+(d[i].pp-d[i-1].pp).toFixed(2);
    d[i].tvc=0;
    var s=Math.max(0,i-71);
    d[i].ifa=+d.slice(s,i+1).reduce(function(a,x){return a+x.pp;},0).toFixed(1);
  }
  for(var j=0;j<d.length;j++){
    var sc=scoreNR(d[j].tvc,d[j].ifa);
    d[j].irc=+(sc.nr/100).toFixed(3);
  }
  return d;
}
function rebuildALLFromRealData(id){
  var rd=buildRealData(id);
  if(!rd||rd.length===0)return false;
  ALL.length=0;
  rd.forEach(function(x){ALL.push(x);});
  simH=Math.min(72,ALL.length-1);
  updUI();updCharts();
  document.querySelectorAll('span').forEach(function(el){
    if(el.textContent.trim()==='SIM'){
      el.textContent='REAL';
      el.style.background='#dcfce7';
      el.style.color='#166534';
    }
  });
  return true;
}
function computeRealNR(id){
  var fd=fcstData[id];
  if(!fd||!fd.ok)return null;
  var realIFA=fd.realIFA||0,prospIFA=fd.prospectivoIFA||0,tvcReal=0;
  if(typeof dgaData!=='undefined'&&dgaData&&dgaData.estaciones){
    var stn=dgaData.estaciones[id];
    if(stn&&stn.q_m3s!==null){
      var prev=_prevQ[id];
      if(prev!==null&&prev!==undefined)tvcReal=Math.max(0,stn.q_m3s-prev);
      _prevQ[id]=stn.q_m3s;
    }
  }
  var nrO=scoreNR(tvcReal,realIFA),nrP=scoreNR(tvcReal,prospIFA);
  return{nrOper:Math.max(nrO.nr,nrP.nr),tvcReal:Math.round(tvcReal*100)/100,
    realIFA:Math.round(realIFA),prospIFA:Math.round(prospIFA)};
}
function updSATHFromRealData(id){
  var rn=computeRealNR(id);if(!rn)return;
  var nr=rn.nrOper;
  var nf=document.getElementById('nr-fill');
  if(nf){nf.style.width=Math.min(100,nr)+'%';
    nf.style.background=nr>=90?'#dc2626':nr>=80?'#ea580c':nr>=70?'#d97706':'#16a34a';}
  var vi=document.getElementById('v-irc');if(vi)vi.textContent=nr;
  if(typeof updSATHSemaphore==='function')updSATHSemaphore(nr);
  var bnn=document.getElementById('bnn');
  var info='IFA obs: '+rn.realIFA+'mm -> prox: '+rn.prospIFA+'mm | TVC DGA: '+rn.tvcReal+' m3/s';
  if(bnn){
    if(nr>=90){bnn.className='bnn bnn-alarma';bnn.style.display='flex';
      bnn.innerHTML='<strong>ALARMA NR '+nr+'/100</strong> | '+info;}
    else if(nr>=80){bnn.className='bnn bnn-alerta';bnn.style.display='flex';
      bnn.innerHTML='<strong>ALERTA NR '+nr+'/100</strong> | '+info;}
    else if(nr>=70){bnn.className='bnn bnn-precaucion';bnn.style.display='flex';
      bnn.innerHTML='<strong>PRECAUCION NR '+nr+'/100</strong> | '+info;}
    else{bnn.style.display='none';bnn.className='bnn';}
  }
}
"""
    TARGET = "\nfunction genData(){"
    if "function buildRealData(" not in html and TARGET in html:
        html = html.replace(TARGET, NR_REAL + TARGET, 1)
        log.append("scoreNR + buildRealData + rebuildALLFromRealData + NR real")

    # ── Hook fetchAllOM: rebuild desde datos reales ──────────────────────
    # Solo agrega rebuildALLFromRealData(activeStn) — NO 'id' aquí
    for old_hook, new_hook in [
        ("await Promise.all(Object.keys(STNS).map(id=>fetchOM(id)));\n  rebuildALLFromRealData(activeStn);\n  updSATHFromRealData(activeStn);\n  renderFc",
         None),  # ya correcto
        ("await Promise.all(Object.keys(STNS).map(id=>fetchOM(id)));\n  renderFc",
         "await Promise.all(Object.keys(STNS).map(id=>fetchOM(id)));\n  rebuildALLFromRealData(activeStn);\n  updSATHFromRealData(activeStn);\n  renderFc"),
    ]:
        if new_hook and old_hook in html and "rebuildALLFromRealData(activeStn)" not in html:
            html = html.replace(old_hook, new_hook)
            log.append("Hook fetchAllOM")
            break

    # ── Hook cambio de estación (usa variable 'id' que SÍ está definida) ─
    for old_h, new_h in [
        ("updRealIFA();\n  updSATHFromRealData(id);\n  fetchFloodForecast",
         "updRealIFA();\n  rebuildALLFromRealData(id);\n  updSATHFromRealData(id);\n  fetchFloodForecast"),
        ("updRealIFA();\n  fetchFloodForecast",
         "updRealIFA();\n  rebuildALLFromRealData(id);\n  updSATHFromRealData(id);\n  fetchFloodForecast"),
    ]:
        if old_h in html and "rebuildALLFromRealData(id)" not in html:
            html = html.replace(old_h, new_h)
            log.append("Hook cambio estacion")
            break

    return html, log, html != orig

def main():
    if not os.path.exists(SATH):
        print(f"ERROR: {SATH} no encontrado"); return 1
    with open(SATH, encoding="utf-8") as f:
        html = f.read()
    print(f"Archivo: {len(html):,} bytes")
    html_new, log, changed = patch(html)

    import re
    scripts = re.findall(r'<script>(.*?)</script>', html_new, re.DOTALL)
    js = scripts[0] if scripts else ''
    op = js.count('{'); cl = js.count('}')
    balanced = op == cl
    print(f"JS balanceado: {balanced} ({{ {op}  }} {cl})")

    if not balanced:
        print("ERROR: JS no balanceado — abortando")
        return 1

    if changed:
        with open(SATH,"w",encoding="utf-8") as f:
            f.write(html_new)
        print(f"Guardado: {len(html_new):,} bytes")
        for l in log: print(f"  [+] {l}")
    else:
        print("Sin cambios necesarios")
    return 0

if __name__=="__main__":
    sys.exit(main())
