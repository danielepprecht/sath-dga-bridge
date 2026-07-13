#!/usr/bin/env python3
"""patch_sath.py — Aplica actualizaciones SATH_v5.html desde GitHub Actions"""
import os, sys

SATH = "docs/SATH_v5.html"

def patch(html):
    orig = html
    log = []

    if "simH=0,paused=false" in html:
        html = html.replace("simH=0,paused=false","simH=72,paused=true",1)
        log.append("simH=72")

    OLD_KEY = "windyKey=sessionStorage.getItem('cogrid_windy_key')||'';"
    NEW_KEY = (OLD_KEY + "\n"
        "['equipo de alerta','sath','COGRID','senapred'].forEach(function(p){\n"
        "  var ow=sessionStorage.getItem(p+'_windy_key');\n"
        "  if(ow&&!windyKey){windyKey=ow;}\n"
        "  var oc=sessionStorage.getItem(p+'_claude_key');\n"
        "  if(oc&&!claudeKey){claudeKey=oc;}\n"
        "});")
    if OLD_KEY in html and "forEach(function" not in html:
        html = html.replace(OLD_KEY, NEW_KEY, 1)
        log.append("Key migration")

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
      el.title='Datos reales Open-Meteo ERA5';
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
  var info='TVC DGA: '+rn.tvcReal+' m3/s | IFA obs: '+rn.realIFA+'mm -> prox: '+rn.prospIFA+'mm';
  if(bnn){
    if(nr>=90){bnn.className='bnn bnn-alarma';bnn.style.display='flex';
      bnn.innerHTML='<strong>ALARMA - NR '+nr+'/100</strong> | '+info;}
    else if(nr>=80){bnn.className='bnn bnn-alerta';bnn.style.display='flex';
      bnn.innerHTML='<strong>ALERTA - NR '+nr+'/100</strong> | '+info;}
    else if(nr>=70){bnn.className='bnn bnn-precaucion';bnn.style.display='flex';
      bnn.innerHTML='<strong>PRECAUCION - NR '+nr+'/100</strong> | '+info;}
    else{bnn.style.display='none';bnn.className='bnn';}
  }
}
"""
    TARGET = "\nfunction genData(){"
    if "function buildRealData(" not in html and TARGET in html:
        html = html.replace(TARGET, NR_REAL + TARGET, 1)
        log.append("scoreNR + buildRealData + rebuildALLFromRealData")

    OLD1 = "await Promise.all(Object.keys(STNS).map(id=>fetchOM(id)));\n  updSATHFromRealData(activeStn);\n  renderFc"
    NEW1 = "await Promise.all(Object.keys(STNS).map(id=>fetchOM(id)));\n  rebuildALLFromRealData(activeStn);\n  updSATHFromRealData(activeStn);\n  renderFc"
    OLD1B = "await Promise.all(Object.keys(STNS).map(id=>fetchOM(id)));\n  renderFc"
    NEW1B = "await Promise.all(Object.keys(STNS).map(id=>fetchOM(id)));\n  rebuildALLFromRealData(activeStn);\n  updSATHFromRealData(activeStn);\n  renderFc"
    if "rebuildALLFromRealData" not in html:
        if OLD1 in html:
            html = html.replace(OLD1, NEW1)
            log.append("Hook fetchAllOM")
        elif OLD1B in html:
            html = html.replace(OLD1B, NEW1B)
            log.append("Hook fetchAllOM (alt)")

    OLD2 = "updRealIFA();\n  updSATHFromRealData(id);\n  fetchFloodForecast"
    NEW2 = "updRealIFA();\n  rebuildALLFromRealData(id);\n  updSATHFromRealData(id);\n  fetchFloodForecast"
    OLD2B = "updRealIFA();\n  fetchFloodForecast"
    NEW2B = "updRealIFA();\n  rebuildALLFromRealData(id);\n  updSATHFromRealData(id);\n  fetchFloodForecast"
    if "rebuildALLFromRealData(id)" not in html:
        if OLD2 in html:
            html = html.replace(OLD2, NEW2)
            log.append("Hook estacion")
        elif OLD2B in html:
            html = html.replace(OLD2B, NEW2B)
            log.append("Hook estacion (alt)")

    return html, log, html != orig

def main():
    if not os.path.exists(SATH):
        print(f"ERROR: {SATH} no encontrado"); return 1
    with open(SATH, encoding="utf-8") as f:
        html = f.read()
    print(f"Archivo: {len(html):,} bytes")
    html_new, log, changed = patch(html)
    if changed:
        with open(SATH,"w",encoding="utf-8") as f:
            f.write(html_new)
        print(f"Guardado: {len(html_new):,} bytes")
        for l in log: print(f"  [+] {l}")
        print("SATH_v5.html actualizado correctamente")
    else:
        print("Sin cambios necesarios - ya estaba actualizado")
    return 0

if __name__=="__main__":
    sys.exit(main())
