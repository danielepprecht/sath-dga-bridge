#!/usr/bin/env python3
"""patch_sath.py — Aplica todos los fixes al SATH_v5.html via GitHub Actions"""
import os, sys, re
from collections import Counter
 
SATH = "docs/SATH_v5.html"
 
def patch(html):
    match = re.search(r'(<script>)(.*?)(</script>)', html, re.DOTALL)
    if not match:
        return html, []
    js = match.group(2)
    orig = js
    log = []
 
    # ── 1. Nombres oficiales DGA ──────────────────────────────────────────
    if 'Leufucade' not in js and 'const STNS' in js:
        old = js[js.find('const STNS'):js.find('};', js.find('const STNS'))+2]
        new = """const STNS = {
  antihue:    {name:'Río Calle-Calle en Antilhue',    cod:'10122002',lat:-39.85,lon:-73.10,cuenca:'Calle-Calle', tipo:'Fluviométrica',access:'dga'},
  rinihue:    {name:'Río San Pedro en Lago Riñihue',  cod:'10111001',lat:-39.79,lon:-72.43,cuenca:'San Pedro',   tipo:'Fluviométrica',access:'dga'},
  mamalona:   {name:'Río San Pedro en Pucono',        cod:'10113003',lat:-39.58,lon:-72.18,cuenca:'San Pedro',   tipo:'Fluviométrica',access:'dga'},
  valdivia:   {name:'Río Cruces en Rucaco',           cod:'10134001',lat:-39.64,lon:-73.09,cuenca:'Cruces',      tipo:'Fluviométrica',access:'dga'},
  corral:     {name:'Est. Meteorológica Corral',      cod:'10200001',lat:-39.88,lon:-73.43,cuenca:'Costero',     tipo:'Meteorológica',access:'dga'},
  lacpicada:  {name:'Río Leufucade en Purulón',       cod:'10133000',lat:-39.82,lon:-73.27,cuenca:'Cruces',      tipo:'Fluviométrica',access:'dga'},
  laslomas:   {name:'Río Negro en Las Lomas',         cod:'10411002',lat:-39.94,lon:-73.02,cuenca:'Bueno sur',   tipo:'Fluviométrica',access:'dga'},
  tegualda:   {name:'Río Toro en Tegualda',           cod:'10351001',lat:-40.17,lon:-72.62,cuenca:'San Pedro',   tipo:'Fluviométrica',access:'dga'},
  panguipulli:{name:'Canal Hueninca - Lago Calafquén',cod:'10107003',lat:-39.64,lon:-72.33,cuenca:'Calle-Calle',tipo:'Fluviométrica',access:'dga'},
  pilmaiquen: {name:'Río Pilmaiquén en San Pablo',    cod:'10328001',lat:-40.18,lon:-72.37,cuenca:'Bueno-Ranco', tipo:'Fluviométrica',access:'dga'},
  launion:    {name:'Río Llollelhue en La Unión',     cod:'10313001',lat:-40.29,lon:-73.09,cuenca:'Bueno',       tipo:'Fluviométrica',access:'dga'},
  riobueno:   {name:'Río Bueno en Bueno',             cod:'10311001',lat:-40.69,lon:-72.97,cuenca:'Bueno',       tipo:'Fluviométrica',access:'dga'},
};"""
        if old and old in js:
            js = js.replace(old, new, 1)
            log.append("Nombres oficiales DGA")
 
    # ── 2. NR unificado: buildRealData incluye satFactor ─────────────────
    if 'd[j].sf=' not in js:
        OLD = """  for(var j=0;j<d.length;j++){
    var sc=scoreNR(Math.max(0,d[j].tvc),d[j].ifa,d[j].apc);
    d[j].irc=+Math.min(1,(sc.nr*sf/100)).toFixed(3);
  }
  return d;
}"""
        NEW = """  var _ifa168=(typeof fcstData!=='undefined'&&fcstData[id])?fcstData[id].realIFA168||0:0;
  var _sf=typeof satFactor==='function'?satFactor(_ifa168):1;
  for(var j=0;j<d.length;j++){
    var sc=scoreNR(Math.max(0,d[j].tvc),d[j].ifa,d[j].apc);
    d[j].irc=+Math.min(1,sc.nr*_sf/100).toFixed(3);
    d[j].sf=+_sf.toFixed(3);
    d[j].ifa168=+_ifa168.toFixed(0);
  }
  return d;
}"""
        if OLD in js:
            js = js.replace(OLD, NEW, 1)
            log.append("NR unificado con satFactor en buildRealData")
        else:
            # Fallback: find simpler pattern
            OLD2 = """  for(var j=0;j<d.length;j++){
    var sc=scoreNR(Math.max(0,d[j].tvc),d[j].ifa,d[j].apc);
    d[j].irc=+(sc.nr/100).toFixed(3);
  }
  return d;
}"""
            NEW2 = """  var _ifa168=(typeof fcstData!=='undefined'&&fcstData[id])?fcstData[id].realIFA168||0:0;
  var _sf=typeof satFactor==='function'?satFactor(_ifa168):1;
  for(var j=0;j<d.length;j++){
    var sc=scoreNR(Math.max(0,d[j].tvc),d[j].ifa,d[j].apc);
    d[j].irc=+Math.min(1,sc.nr*_sf/100).toFixed(3);
    d[j].sf=+_sf.toFixed(3);
    d[j].ifa168=+_ifa168.toFixed(0);
  }
  return d;
}"""
            if OLD2 in js:
                js = js.replace(OLD2, NEW2, 1)
                log.append("NR unificado con satFactor (fallback)")
 
    # ── 3. updUI: satFactor visible en tarjeta NR ─────────────────────────
    if 'sat. IFA7d=' not in js:
        OLD = """  updSATHSemaphore(nr);"""
        NEW = """  updSATHSemaphore(nr);
  if(cur.sf&&cur.sf>1.01){
    const elNRa=document.getElementById('a-irc');
    if(elNRa){const sp=Math.round((cur.sf-1)*100);
      elNRa.textContent=ircAct(cur.irc)+' (+'+sp+'% sat. IFA7d='+cur.ifa168+'mm)';}
  }"""
        if OLD in js:
            js = js.replace(OLD, NEW, 1)
            log.append("satFactor visible en tarjeta NR")
 
    # ── 4. updSATHFromRealData: no sobreescribe NR ────────────────────────
    if 'var nr=rn.nrOper' in js:
        idx = js.find('function updSATHFromRealData(')
        end = js.find('\nfunction ', idx+20)
        old_fn = js[idx:end]
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
  var lbl=i168>350?'Suelo saturado':i168>200?'Suelo muy humedo':i168>100?'Suelo humedo':'Normal';
  var eA=document.getElementById('a-ifa');
  if(eA&&typeof ifaAct==='function')
    eA.innerHTML=ifaAct(rn.realIFA)+
      '<br><small style="color:#7c3aed">IFA 7d: '+Math.round(i168)+'mm | '+lbl+
      (sfP>0?' | +'+sfP+'% NR':'')+
      '</small>';
}"""
        if idx >= 0 and end > idx:
            js = js[:idx] + new_fn + js[end:]
            log.append("updSATHFromRealData: no sobreescribe NR + IFA 7d visible")
 
    # ── 5. Verificar JS balanceado ─────────────────────────────────────────
    op = js.count('{'); cl = js.count('}')
    if op != cl:
        print(f"ERROR JS desbalanceado ({op} vs {cl}) — abortando")
        return html, []
 
    if js == orig:
        return html, log
 
    new_html = html[:match.start(2)] + js + html[match.end(2):]
    return new_html, log
 
def main():
    if not os.path.exists(SATH):
        print(f"AVISO: {SATH} no encontrado — omitiendo"); return 0
    with open(SATH, encoding='utf-8') as f:
        html = f.read()
    print(f"Archivo: {len(html):,} bytes")
    new_html, log = patch(html)
    if log:
        with open(SATH, 'w', encoding='utf-8') as f:
            f.write(new_html)
        print(f"Guardado: {len(new_html):,} bytes")
        for l in log: print(f"  [+] {l}")
    else:
        print("Sin cambios necesarios")
    return 0
 
if __name__ == '__main__':
    sys.exit(main())
