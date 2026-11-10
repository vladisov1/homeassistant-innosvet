/* innosvět: custom Lovelace card, no external dependencies.
 * UX improvement 2026-11-09: highlighted month KPI tiles and persistent, accessible details.
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
        :host { display:block; container-type:inline-size; } ha-card { padding:18px; overflow:hidden; }
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
        .detailbar {display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:18px;margin-bottom:12px;}
        .detailbar label {font-size:14px;font-weight:700;}
        .detailbar select {font:inherit;color:var(--primary-text-color);background:var(--card-background-color);border:1px solid var(--divider-color,#bbb);border-radius:9px;padding:9px 12px;min-width:140px;}
        .detailbar select:focus-visible, button:focus-visible {outline:2px solid var(--primary-color,#7b1267);outline-offset:2px;}
        .month-summary { padding:15px; border-radius:14px; background:color-mix(in srgb, var(--card-background-color,#fff) 93%, #a343a6); border:1px solid color-mix(in srgb,var(--divider-color,#ddd) 70%, #bd80c6); }
        .month-status {display:flex;align-items:center;gap:8px;margin-bottom:14px;flex-wrap:wrap;}
        .month-icon {display:inline-grid;place-items:center;width:31px;height:31px;border-radius:9px;background:#f2ddf4;color:#7b1267;font-size:19px;}
        .month-chip {font-size:12px;font-weight:700;padding:5px 10px;border-radius:20px;background:#eed5f2;color:#63245e;}
        .month-period {font-size:12px;color:var(--secondary-text-color);margin-left:auto;}
        .metrics {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;}
        .metric {min-width:0;min-height:105px;border-radius:12px;padding:13px 12px;display:flex;flex-direction:column;gap:9px;border:1px solid transparent;}
        .metric-cost {background:color-mix(in srgb,var(--card-background-color,#fff) 78%,#dbb0e3);}
        .metric-advance {background:color-mix(in srgb,var(--card-background-color,#fff) 80%,#f6cf8e);}
        .metric-difference {background:color-mix(in srgb,var(--card-background-color,#fff) 78%,#a6d8b1);border-color:#5da970;}
        .metric-difference.unfavorable {background:color-mix(in srgb,var(--card-background-color,#fff) 78%,#f3b7ad);border-color:#d97766;}
        .metric-difference.neutral {background:color-mix(in srgb,var(--card-background-color,#fff) 86%,#b5bdc6);border-color:var(--divider-color,#ccc);}
        .metric-label {display:flex;align-items:center;gap:7px;font-size:12px;line-height:1.35;color:var(--primary-text-color);font-weight:600;}
        .metric-icon {display:inline-flex;align-items:center;justify-content:center;flex:0 0 27px;height:27px;border-radius:50%;background:#eac4ee;color:#722268;font-size:17px;font-weight:700;}
        .metric-advance .metric-icon {background:#fbe0af;color:#8a5300;}
        .metric-difference .metric-icon {background:#42935c;color:#fff;}
        .metric-difference.unfavorable .metric-icon {background:#b74636;}
        .metric-difference.neutral .metric-icon {background:#6c7784;}
        .metric-value {font-weight:800;font-size:clamp(17px,2.9vw,25px);line-height:1.2;letter-spacing:-.02em;font-variant-numeric:tabular-nums;overflow-wrap:anywhere;color:var(--primary-text-color);}
        .metric-difference .metric-value {color:#226d34;}
        .metric-difference.unfavorable .metric-value {color:#a42e26;}
        .metric-difference.neutral .metric-value {color:var(--primary-text-color);}
        .interpretation {display:flex;align-items:center;gap:9px;margin-top:11px;padding:11px 13px;border-radius:10px;font-size:13px;line-height:1.4;font-weight:700;background:color-mix(in srgb,var(--card-background-color,#fff) 78%,#b8e2c2);color:#256e39;}
        .interpretation.unfavorable {background:color-mix(in srgb,var(--card-background-color,#fff) 78%,#f1bab4);color:#a42e26;}
        .interpretation.neutral {background:var(--secondary-background-color);color:var(--primary-text-color);}
        .detailhint {font-size:12px;color:var(--secondary-text-color);margin-top:11px;line-height:1.5;}
        .note {font-size:12px;color:var(--secondary-text-color);margin-top:7px;line-height:1.5;}
        @container(max-width:600px){ha-card{padding:14px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.metric-difference{grid-column:1/-1}.metric{min-height:unset;padding:12px}.metric-value{font-size:22px}.month-period{margin-left:0;width:100%;}.legend{gap:9px}}
        @container(max-width:380px){.metrics{grid-template-columns:1fr}.metric-difference{grid-column:auto}.metric-value{font-size:23px}}
        .error { padding:18px 0; color:var(--error-color); }
      </style><ha-card><div class="top"><h2></h2><div class="switch">
        <button type="button" data-kind="plyn" aria-pressed="true">Plyn</button>
        <button type="button" data-kind="elektrina" aria-pressed="false">Elektřina</button>
      </div></div><div class="sub"></div><div class="graph"></div>
      <div class="legend">
        <span style="--line:#7b1267">Dosavadní náklady</span>
        <span class="dashed" style="--line:#7b1267">Výhled nákladů</span>
        <span style="--line:#e49300">Srovnání podle záloh</span>
      </div><div class="detailbar"><label for="innosvet-month-select">Vybraný měsíc</label><select id="innosvet-month-select" aria-label="Vyberte měsíc pro zobrazení hodnot"></select></div>
      <section class="month-summary" aria-label="Přehled nákladů vybraného měsíce">
        <div class="month-status"><span class="month-icon" aria-hidden="true">▦</span><span class="month-chip"></span><span class="month-period"></span></div>
        <div class="metrics">
          <div class="metric metric-cost"><div class="metric-label"><span class="metric-icon" aria-hidden="true">◉</span>Náklady a odhad</div><div class="metric-value" data-value="cost"></div></div>
          <div class="metric metric-advance"><div class="metric-label"><span class="metric-icon" aria-hidden="true">≡</span>Podle záloh</div><div class="metric-value" data-value="advance"></div></div>
          <div class="metric metric-difference"><div class="metric-label"><span class="metric-icon" aria-hidden="true">↓</span>Rozdíl proti zálohám</div><div class="metric-value" data-value="difference"></div></div>
        </div>
        <div class="interpretation"><span class="interpret-icon" aria-hidden="true">●</span><span class="interpret-text"></span></div>
      </section>
      <div class="detailhint">Částky zůstávají zobrazené. Měsíc lze vybrat v seznamu nebo kliknutím do grafu; přejetí myší výběr nemění.</div>
      <div class="note">Hodnoty jsou výpočtem innogy; aktuální měsíc může zahrnovat odhad. Budoucí body nejsou skutečná spotřeba ani potvrzené platby.</div></ha-card>`;
      this.shadowRoot.querySelector('#innosvet-month-select').addEventListener('change', e => {
        this._pinnedMonth = e.target.value;
        this._selectedMonth = e.target.value;
        this._renderDetailOnly();
      });
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
  _renderDetailOnly() {
    if (!this.shadowRoot || !this._detailData || !this._detailData.length) return;
    const data=this._detailData, iCurrent=this._detailCurrent;
    let idx=data.findIndex(d=>d.month===(this._pinnedMonth || this._selectedMonth));
    if(idx<0) idx=iCurrent>=0?iCurrent:0;
    const d=data[idx];
    this._selectedMonth=d.month;
    const select=this.shadowRoot.querySelector('#innosvet-month-select');
    if (select && select.value!==d.month) select.value=d.month;
    const type = iCurrent>=0 ? (idx>iCurrent?'výhled':idx===iCurrent?'průběžný měsíc':'uzavřený měsíc') : 'měsíční bod';
    const fmt=v=>v.toLocaleString('cs-CZ',{style:'currency',currency:'CZK'});
    const diff=d.cost-d.advance;
    const stateClass=diff<-0.005?'favorable':diff>0.005?'unfavorable':'neutral';
    const month=d.month.slice(5)+'/'+d.month.slice(0,4);
    const status=this.shadowRoot.querySelector('.month-chip');
    if(status) status.textContent=type;
    const period=this.shadowRoot.querySelector('.month-period');
    if(period) period.textContent=month;
    const summary=this.shadowRoot.querySelector('.month-summary');
    if(summary) {
      const values={cost:d.cost,advance:d.advance,difference:diff};
      for(const [key,value] of Object.entries(values)) {
        const node=summary.querySelector(`[data-value="${key}"]`);
        if(node) node.textContent=fmt(value);
      }
      const difference=summary.querySelector('.metric-difference');
      const interpretation=summary.querySelector('.interpretation');
      if(difference) {
        difference.classList.toggle('unfavorable',stateClass==='unfavorable');
        difference.classList.toggle('neutral',stateClass==='neutral');
        const mark=difference.querySelector('.metric-icon');
        if(mark) mark.textContent=stateClass==='favorable'?'↓':stateClass==='unfavorable'?'↑':'=';
      }
      if(interpretation) {
        interpretation.classList.toggle('unfavorable',stateClass==='unfavorable');
        interpretation.classList.toggle('neutral',stateClass==='neutral');
        const message=interpretation.querySelector('.interpret-text');
        const qualifier=type==='výhled'?'Prognóza: ':type==='průběžný měsíc'?'Průběžný odhad: ':'';
        if(message) message.textContent=qualifier+(stateClass==='neutral'?'Náklady odpovídají srovnání podle záloh':stateClass==='favorable'?`O ${fmt(Math.abs(diff))} méně než podle záloh`:`O ${fmt(diff)} více než podle záloh`);
        const mark=interpretation.querySelector('.interpret-icon');
        if(mark) mark.textContent=stateClass==='favorable'?'↘':stateClass==='unfavorable'?'↗':'=';
      }
    }
  }
  _render() {
    if (!this.shadowRoot || !this._config || !this._hass) return;
    const dom = this.shadowRoot;
    const kind = this._selected;
    const entityId = kind === 'plyn' ? this._config.gas_entity : this._config.electricity_entity;
    const state = this._hass.states[entityId];
    dom.querySelector('h2').textContent = this._config.title || 'Vývoj nákladů innosvět';
    dom.querySelectorAll('button[data-kind]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.kind === kind)));
    const graph = dom.querySelector('.graph'), sub = dom.querySelector('.sub');
    if (!state) { if (!this._detailData) graph.innerHTML='<div class="error">Senzor nebyl nalezen. Zkontrolujte entity_id v konfiguraci karty.</div>'; return; }
    const a = state.attributes || {}, raw = a.body_grafu;
    if (!Array.isArray(raw) || raw.length !== 13) {
      this._renderSignature = null; graph.replaceChildren(); sub.textContent=''; graph.innerHTML='<div class="error">Chybí 13 měsíčních bodů. Zapněte finance_extra_enabled a ověřte načtení grafu.</div>'; return;
    }
    const data = raw.map(x => ({month:String(x.mesic || ''), cost:Number(x.naklady_kc), advance:Number(x.podle_zaloh_kc)}));
    if (!data.every(x => /^\d{4}-(0[1-9]|1[0-2])$/.test(x.month) && Number.isFinite(x.cost) && Number.isFinite(x.advance))) {
      this._renderSignature = null; graph.replaceChildren(); sub.textContent=''; graph.innerHTML='<div class="error">Data grafu nejsou platná.</div>'; return;
    }
    const current = String(a.mesic_zobrazenych_nakladu || '');
    const iCurrent = data.findIndex(x => x.month === current);
    // Home Assistant sets `hass` frequently, even if these 13 points did not change.
    // Rebuilding the SVG during a pointer interaction causes flickering/lost details.
    const signature = JSON.stringify([kind, this._config.title || '', current, a.graf_zacatek || '', data]);
    if (this._renderSignature === signature) { this._renderDetailOnly(); return; }
    this._renderSignature = signature;
    this._detailData=data;
    this._detailCurrent=iCurrent;
    const monthSelect=dom.querySelector('#innosvet-month-select');
    if (monthSelect) {
      monthSelect.replaceChildren();
      data.forEach(d => {const option=document.createElement('option'); option.value=d.month; option.textContent=d.month.slice(5)+'/'+d.month.slice(0,4); monthSelect.appendChild(option);});
    }
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
    const chooseMonth=i=>{
      if (i<0 || i>=data.length) return;
      this._selectedMonth=data[i].month;
      this._pinnedMonth=data[i].month;
      this._renderDetailOnly();
    };
    data.forEach((d,i)=>{
      const r = this._selectedMonth===d.month ? 6 : 4;
      const hit=add('circle',{cx:X(i),cy:Y(d.cost),r,fill:'#7b1267',stroke:'var(--card-background-color, white)','stroke-width':1.2});
      const target=add('circle',{cx:X(i),cy:Y(d.cost),r:18,fill:'transparent',tabindex:0,role:'button','aria-label':`${d.month}: ${fmt(d.cost)}`});
      target.style.cursor='pointer';
      target.addEventListener('click',()=>chooseMonth(i));
      target.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();chooseMonth(i);}});
      hit.style.pointerEvents='none';
    });
    // Hover no longer changes the selected month. The detail panel is permanent.
    // The whole plot is selectable, not only tiny points on the line.
    svg.addEventListener('click',e=>{
      const rect=svg.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const x=(e.clientX-rect.left)/rect.width*W;
      const y=(e.clientY-rect.top)/rect.height*H;
      if (x<L || x>W-R || y<T || y>T+plotH) return;
      const idx=Math.max(0,Math.min(12,Math.round((x-L)*12/plotW)));
      chooseMonth(idx);
    });
    svg.addEventListener('keydown',e=>{
      if(e.target!==svg || !['ArrowLeft','ArrowRight'].includes(e.key)) return;
      e.preventDefault();
      const idx=data.findIndex(d=>d.month===this._selectedMonth);
      const next=Math.max(0,Math.min(12,(idx<0?(iCurrent<0?0:iCurrent):idx)+(e.key==='ArrowRight'?1:-1)));
      chooseMonth(next);
    });
    graph.append(svg);
    const preferred=this._pinnedMonth || this._selectedMonth;
    const preferredIndex=preferred ? data.findIndex(x=>x.month===preferred) : -1;
    this._selectedMonth=data[preferredIndex>=0 ? preferredIndex : (iCurrent>=0?iCurrent:0)].month;
    this._renderDetailOnly();
  }
}
if (!customElements.get('innosvet-cost-chart')) customElements.define('innosvet-cost-chart',InnosvetCostChart);
window.customCards = window.customCards || [];
if (!window.customCards.some(x=>x.type==='innosvet-cost-chart')) window.customCards.push({type:'innosvet-cost-chart',name:'innosvět · Vývoj nákladů',description:'Plyn a elektřina podle 13 měsíčních bodů portálu innosvět'});
