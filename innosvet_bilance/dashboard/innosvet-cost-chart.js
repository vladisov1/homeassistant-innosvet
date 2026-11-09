/* innosvět: custom Lovelace card, no external dependencies.
 * The source is the existing 13-point MQTT sensor attribute `body_grafu`.
 * `naklady_kc` is a supplier estimate, NOT independently verified real-world consumption.
 */
class InnosvetCostChart extends HTMLElement {
  setConfig(config) {
    if (!config || typeof config.gas_entity !== 'string' || typeof config.electricity_entity !== 'string') {
      throw new Error('innosvět: vyplňte gas_entity a electricity_entity.');
    }
    this._config = config;
    this._selected ??= 'plyn';
    // Preserve the inspected month when HA re-applies the same card configuration.
    this._selectedMonth ??= null;
    this._pinnedMonth ??= null;
    if (!this.shadowRoot) {
      this.attachShadow({mode:'open'});
      this.shadowRoot.innerHTML = `<style>
        :host { display:block; } ha-card { padding:18px; overflow:hidden; }
        .top { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px; }
        h2 { margin:0; font-size:18px; font-weight:600; }
        .switch { display:flex; gap:4px; background:var(--secondary-background-color); border-radius:9px; padding:3px; }
        button { font:inherit; border:0; border-radius:7px; padding:7px 13px; cursor:pointer; color:var(--primary-text-color); background:transparent; }
        button[aria-pressed="true"] { background:var(--card-background-color); box-shadow:0 1px 4px #0002; font-weight:600; }
        .sub { margin:6px 0 12px; font-size:12px; color:var(--secondary-text-color); }
        svg { width:100%; height:auto; display:block; overflow:visible; touch-action:pan-y; }
        .legend { display:flex; gap:14px; flex-wrap:wrap; font-size:12px; margin-top:10px; }
        .legend span::before { content:''; display:inline-block; width:20px; height:0; border-top:3px solid var(--line); vertical-align:middle; margin-right:6px; }
        .legend .dashed::before { border-top-style:dashed; }
        .info { min-height:44px; margin-top:10px; font-size:13px; color:var(--primary-text-color); line-height:1.5; }
        .note { font-size:12px; color:var(--secondary-text-color); margin-top:4px; }
        .error { padding:18px 0; color:var(--error-color); }
      </style><ha-card><div class="top"><h2></h2><div class="switch">
        <button type="button" data-kind="plyn" aria-pressed="true">Plyn</button>
        <button type="button" data-kind="elektrina" aria-pressed="false">Elektřina</button>
      </div></div><div class="sub"></div><div class="graph"></div>
      <div class="legend">
        <span style="--line:#7b1267">Dosavadní náklady</span>
        <span class="dashed" style="--line:#7b1267">Výhled nákladů</span>
        <span style="--line:#e49300">Srovnání podle záloh</span>
      </div><div class="info" aria-live="polite"></div>
      <div class="note">Hodnoty jsou výpočtem innogy; aktuální měsíc může zahrnovat odhad. Budoucí body nejsou skutečná spotřeba ani potvrzené platby.</div></ha-card>`;
      this.shadowRoot.querySelectorAll('button[data-kind]').forEach(b => b.addEventListener('click', () => {
        this._selected = b.dataset.kind;
        this._selectedMonth = null;
        this._pinnedMonth = null;
        this._render();
      }));
    }
    this._render();
  }
  set hass(value) { this._hass = value; this._render(); }
  getCardSize() { return 5; }
  static getStubConfig() { return {
    type:'custom:innosvet-cost-chart',
    gas_entity:'sensor.innogy_innosvet_innosvet_plyn_dosavadni_naklady_innogy',
    electricity_entity:'sensor.innogy_innosvet_innosvet_elektrina_dosavadni_naklady_innogy'
  }; }
  _render() {
    if (!this.shadowRoot || !this._config || !this._hass) return;
    const dom = this.shadowRoot;
    const kind = this._selected;
    const entityId = kind === 'plyn' ? this._config.gas_entity : this._config.electricity_entity;
    const state = this._hass.states[entityId];
    dom.querySelector('h2').textContent = this._config.title || 'Vývoj nákladů innosvět';
    dom.querySelectorAll('button[data-kind]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.kind === kind)));
    const graph = dom.querySelector('.graph'), info = dom.querySelector('.info'), sub = dom.querySelector('.sub');
    if (!state) { this._renderSignature = null; graph.replaceChildren(); info.textContent = ''; sub.textContent=''; graph.innerHTML='<div class="error">Senzor nebyl nalezen. Zkontrolujte entity_id v konfiguraci karty.</div>'; return; }
    const a = state.attributes || {}, raw = a.body_grafu;
    if (!Array.isArray(raw) || raw.length !== 13) {
      this._renderSignature = null; graph.replaceChildren(); info.textContent = ''; sub.textContent=''; graph.innerHTML='<div class="error">Chybí 13 měsíčních bodů. Zapněte finance_extra_enabled a ověřte načtení grafu.</div>'; return;
    }
    const data = raw.map(x => ({month:String(x.mesic || ''), cost:Number(x.naklady_kc), advance:Number(x.podle_zaloh_kc)}));
    if (!data.every(x => /^\d{4}-(0[1-9]|1[0-2])$/.test(x.month) && Number.isFinite(x.cost) && Number.isFinite(x.advance))) {
      this._renderSignature = null; graph.replaceChildren(); info.textContent = ''; sub.textContent=''; graph.innerHTML='<div class="error">Data grafu nejsou platná.</div>'; return;
    }
    const current = String(a.mesic_zobrazenych_nakladu || '');
    const iCurrent = data.findIndex(x => x.month === current);
    // Home Assistant sets `hass` frequently, even if these 13 points did not change.
    // Rebuilding the SVG during a pointer interaction causes flickering/lost details.
    const signature = JSON.stringify([kind, this._config.title || '', current,
      a.updated_at || '', a.graf_zacatek || '', data]);
    if (this._renderSignature === signature) return;
    this._renderSignature = signature;
    graph.replaceChildren();
    const lastUpdated = a.updated_at && !Number.isNaN(Date.parse(a.updated_at)) ? new Date(a.updated_at).toLocaleString('cs-CZ') : 'nezjištěno';
    const periodStart = /^\d{4}-\d{2}-\d{2}$/.test(String(a.graf_zacatek || '')) ? ` · období od ${a.graf_zacatek.split('-').reverse().join('.')}` : '';
    sub.textContent = `${kind === 'plyn' ? 'Plyn' : 'Elektřina'} · 13 měsíčních bodů${periodStart} · aktualizováno ${lastUpdated}`;
    const NS='http://www.w3.org/2000/svg';
    const svg=document.createElementNS(NS,'svg');
    svg.setAttribute('viewBox','0 0 740 330');
    svg.setAttribute('role','img');
    svg.setAttribute('aria-label',`Vývoj nákladů ${kind}, korunové částky, od ${data[0].month} do ${data[12].month}. Kliknutím vyberete měsíc.`);
    svg.setAttribute('tabindex','0');
    const W=740,H=330,L=76,R=18,T=29,B=48, plotW=W-L-R,plotH=H-T-B;
    const max=Math.max(...data.flatMap(x=>[x.cost,x.advance]),1)*1.08;
    const X=i=>L+i*plotW/12, Y=v=>T+plotH*(1-v/max);
    const add=(tag,attrs={},label)=>{const el=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,String(v)));if(label!==undefined)el.textContent=label;svg.appendChild(el);return el;};
    const colorText='var(--secondary-text-color)';
    const fmt=v=>v.toLocaleString('cs-CZ',{style:'currency',currency:'CZK'});
    for(let n=0;n<=4;n++) {
      const v=max*n/4,y=Y(v);
      add('line',{x1:L,x2:W-R,y1:y,y2:y,stroke:'var(--divider-color, #bbb)','stroke-opacity':'.45'});
      add('text',{x:L-9,y:y+4,'text-anchor':'end',fill:colorText,'font-size':12},Math.round(v).toLocaleString('cs-CZ'));
    }
    data.forEach((d,i)=>add('text',{x:X(i),y:H-21,'text-anchor':'middle',fill:colorText,'font-size':11},d.month.slice(5)+'/'+d.month.slice(2,4)));
    // Future periods begin AFTER the current month; its data point is not a closed actual.
    if(iCurrent>=0 && iCurrent<12){
      const boundary=(X(iCurrent)+X(iCurrent+1))/2;
      add('rect',{x:boundary,y:T,width:W-R-boundary,height:plotH,fill:'var(--secondary-background-color)',opacity:'.65'});
      add('line',{x1:boundary,x2:boundary,y1:T,y2:T+plotH,stroke:'var(--secondary-text-color)','stroke-dasharray':'4 4'});
      add('text',{x:boundary+7,y:T+12,fill:colorText,'font-size':11},'výhled');
    }
    const line=(field,color,from,to,dash='')=>{
      if(to<from) return;
      const path=data.slice(from,to+1).map((d,i)=>`${i?'L':'M'}${X(from+i).toFixed(2)},${Y(d[field]).toFixed(2)}`).join(' ');
      add('path',{d:path,fill:'none',stroke:color,'stroke-width':3,'stroke-linecap':'round',...(dash?{'stroke-dasharray':dash}:{})});
    };
    line('advance','#e49300',0,12);
    const lastHistorical = iCurrent<0 ? 12 : iCurrent;
    line('cost','#7b1267',0,lastHistorical);
    if(iCurrent>=0 && iCurrent<12) line('cost','#7b1267',iCurrent,12,'5 6');
    if(iCurrent>=0){
      const x=X(iCurrent), y=Y(data[iCurrent].cost);
      add('circle',{cx:x,cy:y,r:7,fill:'#7b1267',stroke:'var(--card-background-color, white)','stroke-width':2});
      add('text',{x:x+9,y:y-12,fill:'#7b1267','font-size':12,'font-weight':600},'aktuální měsíc');
    }
    const showMonth=i=>{
      if(i<0 || i>=data.length) return;
      this._selectedMonth = data[i].month;
      const d=data[i];
      const label=iCurrent>=0 ? (i>iCurrent?'výhled':i===iCurrent?'průběžný měsíc':'minulý měsíc') : 'měsíční bod';
      info.textContent=`${d.month.slice(5)}/${d.month.slice(0,4)} (${label}) · náklady / odhad: ${fmt(d.cost)} · podle záloh: ${fmt(d.advance)} · rozdíl: ${fmt(d.cost-d.advance)}`;
    };
    data.forEach((d,i)=>{
      const r = this._selectedMonth===d.month ? 6 : 4;
      const hit=add('circle',{cx:X(i),cy:Y(d.cost),r,fill:'#7b1267',stroke:'var(--card-background-color, white)','stroke-width':1.2});
      const target=add('circle',{cx:X(i),cy:Y(d.cost),r:18,fill:'transparent',tabindex:0,role:'button','aria-label':`${d.month}: ${fmt(d.cost)}`});
      target.style.cursor='pointer';
      target.addEventListener('click',()=>{this._pinnedMonth=d.month;showMonth(i);});
      target.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();this._pinnedMonth=d.month;showMonth(i);}});
      hit.style.pointerEvents='none';
    });
    let hoverIndex = -1;
    svg.addEventListener('pointermove',e=>{
      const rect=svg.getBoundingClientRect();
      if (!rect.width) return;
      const xv=(e.clientX-rect.left)/rect.width*W;
      const i=Math.max(0,Math.min(12,Math.round((xv-L)*12/plotW)));
      if (i !== hoverIndex) { hoverIndex = i; showMonth(i); }
    });
    // The whole plot is selectable, not only tiny points on the line.
    svg.addEventListener('click',e=>{
      const rect=svg.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const x=(e.clientX-rect.left)/rect.width*W;
      const y=(e.clientY-rect.top)/rect.height*H;
      if (x<L || x>W-R || y<T || y>T+plotH) return;
      const idx=Math.max(0,Math.min(12,Math.round((x-L)*12/plotW)));
      this._pinnedMonth=data[idx].month;
      showMonth(idx);
    });
    svg.addEventListener('pointerleave',()=>{
      hoverIndex = -1;
      // Restore the clicked month; if none was clicked, keep the last value visible.
      if (this._pinnedMonth) {
        const idx=data.findIndex(x=>x.month===this._pinnedMonth);
        if (idx>=0) showMonth(idx);
      }
    });
    svg.addEventListener('keydown',e=>{
      if(e.target!==svg || !['ArrowLeft','ArrowRight'].includes(e.key)) return;
      e.preventDefault();
      const idx=data.findIndex(d=>d.month===this._selectedMonth);
      const next=Math.max(0,Math.min(12,(idx<0?(iCurrent<0?0:iCurrent):idx)+(e.key==='ArrowRight'?1:-1)));
      this._pinnedMonth=data[next].month;
      showMonth(next);
    });
    graph.append(svg);
    const preferred=this._pinnedMonth || this._selectedMonth;
    const preferredIndex=preferred ? data.findIndex(x=>x.month===preferred) : -1;
    showMonth(preferredIndex>=0 ? preferredIndex : (iCurrent>=0?iCurrent:0));
  }
}
if (!customElements.get('innosvet-cost-chart')) customElements.define('innosvet-cost-chart',InnosvetCostChart);
window.customCards = window.customCards || [];
if (!window.customCards.some(x=>x.type==='innosvet-cost-chart')) window.customCards.push({type:'innosvet-cost-chart',name:'innosvět · Vývoj nákladů',description:'Plyn a elektřina podle 13 měsíčních bodů portálu innosvět'});
