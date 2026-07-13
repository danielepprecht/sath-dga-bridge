#!/usr/bin/env python3
"""patch_sath.py - Actualiza SATH_v5.html con NR real + Windy fix"""
import os, sys

SATH = "docs/SATH_v5.html"

def main():
    if not os.path.exists(SATH):
        print(f"No encontrado: {SATH}"); return 1

    with open(SATH, encoding="utf-8") as f:
        html = f.read()

    print(f"Archivo actual: {len(html):,} bytes")
    orig = html

    # ── 1. simH=15 por defecto (muestra evento activo al cargar) ──────
    if "simH=0,paused=false" in html:
        html = html.replace("simH=0,paused=false", "simH=15,paused=true", 1)
        print("  [+] simH=15")

    # ── 2. Key migration (restaura Windy/Claude keys renombradas) ──────
    OLD_KEY_LINE = "windyKey=sessionStorage.getItem('equipo de alerta_windy_key')||'';"
    MIGRATION = (
        OLD_KEY_LINE + "\n"
        "// Migracion automatica de claves anteriores\n"
        "['cogrid','sath','COGRID','senapred'].forEach(function(p){\n"
        "  var ow=sessionStorage.getItem(p+'_windy_key');\n"
        "  if(ow&&!windyKey){windyKey=ow;sessionStorage.setItem('equipo de alerta_windy_key',ow);}\n"
        "  var oc=sessionStorage.getItem(p+'_claude_key');\n"
        "  if(oc&&!claudeKey){claudeKey=oc;sessionStorage.setItem('equipo de alerta_claude_key',oc);}\n"
        "});"
    )
    if OLD_KEY_LINE in html and "Migracion automatica" not in html:
        html = html.replace(OLD_KEY_LINE, MIGRATION, 1)
        print("  [+] Key migration Windy/Claude")

    # ── 3. NR desde datos reales (scoreNR + computeRealNR + updSATH) ──
    NR_BLOCK = """
// === NR REAL desde Open-Meteo + DGA Bridge ===
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
function computeRealNR(id){
  var fd=fcstData[id];
  if(!fd||!fd.ok)return null;
  var realIFA=fd.realIFA||0,prospIFA=fd.prospectivoIFA||0,tvcReal=0;
  if(typeof dgaData!=="undefined"&&dgaData&&dgaData.estaciones){
    var stn=dgaData.estaciones[id];
    if(stn&&stn.q_m3s!==null){
      var prev=_prevQ[id];
      if(prev!==null&&prev!==undefined)tvcReal=Math.max(0,stn.q_m3s-prev);
      _prevQ[id]=stn.q_m3s;
    }
  }
  var nrO=scoreNR(tvcReal,realIFA),nrP=scoreNR(tvcReal,prospIFA);
  return{nrOper:Math.max(nrO.nr,nrP.nr),ts:Math.max(nrO.ts,nrP.ts),
    is_:Math.max(nrO.is_,nrP.is_),tvcReal:Math.round(tvcReal*100)/100,
    realIFA:Math.round(realIFA),prospIFA:Math.round(prospIFA)};
}
function updSATHFromRealData(id){
  var rn=computeRealNR(id);if(!rn)return;
  var nr=rn.nrOper;
  var nf=document.getElementById('nr-fill');
  if(nf){nf.style.width=Math.min(100,nr)+'%';
    nf.style.background=nr>=90?'#dc2626':nr>=80?'#ea580c':nr>=70?'#d97706':'#16a34a';}
  var vi=document.getElementById('v-irc');if(vi)vi.textContent=nr;
  updSATHSemaphore(nr);
  var a=alrt(nr/100),bg=document.getElementById('badge');
  if(bg){bg.className='badge '+a.cls+(nr>=70?' pulse':'');
    bg.innerHTML='<i class="ti '+a.icon+'"></i> '+a.txt;}
  var bnn=document.getElementById('bnn');
  var info='TVC DGA: '+rn.tvcReal+' m3/s*h | IFA obs: '+rn.realIFA+'mm -> prox: '+rn.prospIFA+'mm';
  if(bnn){
    if(nr>=90){bnn.className='bnn bnn-alarma';bnn.style.display='flex';
      bnn.innerHTML='<strong>ALARMA - NR '+nr+'/100</strong> | '+info;}
    else if(nr>=80){bnn.className='bnn bnn-alerta';bnn.style.display='flex';
      bnn.innerHTML='<strong>ALERTA - NR '+nr+'/100</strong> | '+info;}
    else if(nr>=70){bnn.className='bnn bnn-precaucion';bnn.style.display='flex';
      bnn.innerHTML='<strong>PRECAUCION - NR '+nr+'/100</strong> | '+info;}
    else{bnn.style.display='none';bnn.className='bnn';}
  }
  var ei=document.getElementById('v-ifa');if(ei)ei.textContent=rn.realIFA;
}
"""
    TARGET = "\nfunction genData(){"
    if "function scoreNR(" not in html and TARGET in html:
        html = html.replace(TARGET, NR_BLOCK + TARGET, 1)
        print("  [+] scoreNR / computeRealNR / updSATHFromRealData")

    # ── 4. Hook: actualizar NR despues de fetchAllOM ───────────────────
    OLD_HOOK1 = "await Promise.all(Object.keys(STNS).map(id=>fetchOM(id)));\n  renderFc"
    NEW_HOOK1 = "await Promise.all(Object.keys(STNS).map(id=>fetchOM(id)));\n  updSATHFromRealData(activeStn);\n  renderFc"
    if OLD_HOOK1 in html and "updSATHFromRealData(activeStn)" not in html:
        html = html.replace(OLD_HOOK1, NEW_HOOK1)
        print("  [+] Hook fetchAllOM")

    # ── 5. Hook: actualizar NR al cambiar estacion ─────────────────────
    OLD_HOOK2 = "updRealIFA();\n  fetchFloodForecast(id);\n  fetchDGABridge();"
    NEW_HOOK2 = "updRealIFA();\n  updSATHFromRealData(id);\n  fetchFloodForecast(id);\n  fetchDGABridge();"
    if OLD_HOOK2 in html and "updSATHFromRealData(id)" not in html:
        html = html.replace(OLD_HOOK2, NEW_HOOK2)
        print("  [+] Hook cambio estacion")

    if html != orig:
        with open(SATH, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  Guardado: {len(html):,} bytes")
        print("SATH_v5.html actualizado correctamente")
    else:
        print("Sin cambios — ya estaba actualizado")
    return 0

if __name__ == "__main__":
    sys.exit(main())
