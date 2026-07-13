#!/usr/bin/env python3
"""patch_sath.py — Aplica y corrige SATH_v5.html — versión limpia"""
import os, sys, re
from collections import Counter
 
SATH = "docs/SATH_v5.html"
 
NR_BLOCK = """
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
  var info='IFA obs: '+rn.realIFA+'mm -> prox: '+rn.prospIFA+'mm';
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
 
def remove_duplicate_nr_blocks(js):
    """Elimina TODOS los bloques NR duplicados del JS y deja solo uno."""
    # Marcadores del bloque NR que el parche inyecta
    START = "// === NR REAL + buildRealData"
    END_MARKER = "function updSATHFromRealData(id){"
 
    positions = [m.start() for m in re.finditer(re.escape(START), js)]
    if len(positions) <= 1:
        return js, False  # sin duplicados
 
    # Encontrar el fin del último bloque updSATHFromRealData
    def find_block_end(js, start):
        idx = js.find(END_MARKER, start)
        if idx < 0: return start + 100
        # Buscar la } de cierre de la función
        depth = 0
        for i in range(idx, min(idx+3000, len(js))):
            if js[i] == '{': depth += 1
            elif js[i] == '}':
                depth -= 1
                if depth == 0: return i + 1
        return idx + 500
 
    # Eliminar todos los bloques excepto el último
    blocks_to_remove = positions[:-1]  # mantener el último
    for pos in reversed(blocks_to_remove):
        end = find_block_end(js, pos)
        js = js[:pos] + js[end:]
 
    return js, True
 
 
def patch(html):
    log = []
 
    # Extraer JS
    match = re.search(r'(<script>)(.*?)(</script>)', html, re.DOTALL)
    if not match:
        print("ERROR: no se encontró bloque <script>"); return html, log
    pre, js, post = match.group(1), match.group(2), match.group(3)
    orig_js = js
 
    # ── 1. Eliminar duplicados const NR_CAL / _prevQ / funciones ─────────
    js, removed = remove_duplicate_nr_blocks(js)
    if removed:
        log.append("Eliminados bloques NR duplicados (fix SyntaxError const)")
 
    # ── 2. Eliminar bug: id no definido en fetchAllOM ─────────────────────
    bad = ("  rebuildALLFromRealData(id);\n"
           "  updSATHFromRealData(id);\n"
           "  fetchFloodForecast(activeStn);")
    ok  = "  fetchFloodForecast(activeStn);"
    if bad in js:
        js = js.replace(bad, ok, 1)
        log.append("Eliminado id-no-definido en fetchAllOM")
 
    # ── 3. Asegurar que el bloque NR existe (exactamente una vez) ─────────
    if "function buildRealData(" not in js:
        target = "\nfunction genData(){"
        if target in js:
            js = js.replace(target, NR_BLOCK + target, 1)
            log.append("Inyectado bloque NR REAL")
 
    # ── 4. Hook fetchAllOM (solo si no está ya) ───────────────────────────
    old_fa = "await Promise.all(Object.keys(STNS).map(id=>fetchOM(id)));\n  renderFc"
    new_fa = "await Promise.all(Object.keys(STNS).map(id=>fetchOM(id)));\n  rebuildALLFromRealData(activeStn);\n  updSATHFromRealData(activeStn);\n  renderFc"
    if old_fa in js and "rebuildALLFromRealData(activeStn)" not in js:
        js = js.replace(old_fa, new_fa)
        log.append("Hook fetchAllOM")
 
    # ── 5. Hook cambio estación ───────────────────────────────────────────
    old_stn = "updRealIFA();\n  fetchFloodForecast"
    new_stn = "updRealIFA();\n  rebuildALLFromRealData(id);\n  updSATHFromRealData(id);\n  fetchFloodForecast"
    if old_stn in js and "rebuildALLFromRealData(id)" not in js:
        js = js.replace(old_stn, new_stn)
        log.append("Hook cambio estacion")
 
    # ── 6. Verificar JS balanceado ────────────────────────────────────────
    op = js.count('{'); cl = js.count('}')
    if op != cl:
        print(f"ERROR JS no balanceado ({op} vs {cl}) — abortando")
        return html, []
 
    # ── 7. Verificar no quedan const duplicados en scope global ──────────
    top_consts = re.findall(r'(?:^|\n)const\s+(\w+)\s*=', js)
    dup = {k:v for k,v in Counter(top_consts).items() if v > 1}
    if dup:
        print(f"ADVERTENCIA: consts duplicados en scope global: {dup}")
 
    if js == orig_js:
        return html, log
 
    new_html = html[:match.start()] + pre + js + post + html[match.end():]
    return new_html, log
 
def main():
    from collections import Counter
    if not os.path.exists(SATH):
        print(f"ERROR: {SATH} no encontrado"); return 1
    with open(SATH, encoding="utf-8") as f:
        html = f.read()
    print(f"Archivo: {len(html):,} bytes")
    new_html, log = patch(html)
    if log:
        with open(SATH,"w",encoding="utf-8") as f:
            f.write(new_html)
        print(f"Guardado: {len(new_html):,} bytes")
        for l in log: print(f"  [+] {l}")
    else:
        print("Sin cambios")
    return 0
 
if __name__=="__main__":
    sys.exit(main())
