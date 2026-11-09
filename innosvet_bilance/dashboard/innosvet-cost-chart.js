/* innosvět – náklady. Native Lovelace custom card, no external dependencies.
 * Reads public MQTT sensor attributes supplied by the user's own HA instance.
 */
class InnosvetCostChart extends HTMLElement {
  setConfig(config) {
    if (!config || typeof config.gas_entity !== 'string' || typeof config.electricity_entity !== 'string') {
      throw new Error('innosvět: vyplňte gas_entity a electricity_entity (entity_id senzorů dosavadních nákladů).');
    }
    this._config = config;
    this._selected = 'plyn';
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
        svg { width:100%; height:auto; display:block; overflow:visible; }
        .legend { display:flex; gap:16px; flex-wrap:wrap; font-size:12px; margin-top:10px; }
        .legend span::before { content:''; display:inline-block; width:18px; height:3px; background:var(--line); vertical-align:middle; margin-right:6px; }
        .info { min-height:20px; margin-top:10px; font-size:13px; color:var(--secondary-text-color); }
        .error { padding:18px 0; color:var(--error-color); }
      </style><ha-card><div class="top"><h2></h2><div class="switch">
        <button type="button" data-kind="plyn" aria-pressed="true">Plyn</button>
        <button type="button" data-kind="elektrina" aria-pressed="false">Elektřina</button>
      </div></div><div class="sub"></div><div class="graph"></div>
      <div class="legend"><span style="--line:#1683b0">Náklady a odhad</span><span style="--line:#d28b21">Srovnání podle záloh</span></div>
      <div class="info" aria-live="polite"></div></ha-card>`;
      this.shadowRoot.querySelectorAll('button[data-kind]').forEach(b => b.addEventListener('click', () => {
        this._selected = b.dataset.kind; this._render();
      }));
    }
    this._render();
  }
  set hass(value) { this._hass = value; this._render(); }
  getCardSize() { return 5; }
  static getStubConfig() { return {type:'custom:innosvet-cost-chart', gas_entity:'sensor.innosvet_plyn_dosavadni_naklady_innogy', electricity_entity:'sensor.innosvet_elektrina_dosavadni_naklady_innogy'}; }
  _render() {
    if (!this.shadowRoot || !this._config || !this._hass) return;
    const dom = this.shadowRoot;
    const kind = this._selected;
    const entityId = kind === 'plyn' ? this._config.gas_entity : this._config.electricity_entity;
    const state = this._hass.states[entityId];
    dom.querySelector('h2').textContent = this._config.title || 'innosvět · Vývoj nákladů';
    dom.querySelectorAll('button[data-kind]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.kind === kind)));
    const graph = dom.querySelector('.graph'), info = dom.querySelector('.info'), sub = dom.querySelector('.sub');
    graph.replaceChildren(); info.textContent = '';
    if (!state) { sub.textContent=''; graph.innerHTML='<div class="error">Senzor nebyl nalezen. Zkontrolujte entity_id v konfiguraci karty.</div>'; return; }
    const a = state.attributes || {};
    const raw = a.body_grafu;
    if (!Array.isArray(raw) || raw.length !== 13) {
      sub.textContent=''; graph.innerHTML='<div class="error">Chybí 13 měsíčních bodů. Zapněte finance_extra_enabled a ověřte načtení grafu.</div>'; return;
    }
    const data = raw.map(x => ({month:String(x.mesic || ''), cost:Number(x.naklady_kc), advance:Number(x.podle_zaloh_kc)}));
    if (!data.every(x => /^\d{4}-(0[1-9]|1[0-2])$/.test(x.month) && Number.isFinite(x.cost) && Number.isFinite(x.advance))) {
      sub.textContent=''; graph.innerHTML='<div class="error">Data grafu nejsou platná.</div>'; return;
    }
    const current = String(a.mesic_zobrazenych_nakladu || '');
    const lastUpdated = a.updated_at ? new Date(a.updated_at).toLocaleString('cs-CZ') : 'nezjištěno';
    sub.textContent = `${kind === 'plyn' ? 'Plyn' : 'Elektřina'} · 13 měsíčních bodů · aktualizováno ${lastUpdated}`;
    const NS='http://www.w3.org/2000/svg';
    const svg=document.createElementNS(NS,'svg');
    svg.setAttribute('viewBox','0 0 740 330');
    svg.setAttribute('role','img');
    svg.setAttribute('aria-label',`Vývoj nákladů ${kind}, částky v korunách, od ${data[0].month} do ${data[12].month}`);
    const W=740,H=330,L=72,R=17,T=24,B=47;
    const plotW=W-L-R,plotH=H-T-B;
    const max=Math.max(...data.flatMap(x=>[x.cost,x.advance]),1)*1.08;
    const X=i=>L+i*plotW/12, Y=v=>T+plotH*(1-v/max);
    const add=(tag,attrs={},label)=>{const el=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,String(v)));if(label!==undefined)el.textContent=label;svg.appendChild(el);return el;};
    const colorText='var(--secondary-text-color)';
    for(let n=0;n<=4;n++) {
      const v=max*n/4,y=Y(v);
      add('line',{x1:L,x2:W-R,y1:y,y2:y,stroke:'var(--divider-color, #bbb)', 'stroke-opacity':'.38'});
      add('text',{x:L-8,y:y+4,'text-anchor':'end',fill:colorText,'font-size':12},Math.round(v).toLocaleString('cs-CZ'));
    }
    data.forEach((d,i)=>{
      const label=d.month.slice(5)+'/'+d.month.slice(2,4);
      add('text',{x:X(i),y:H-21,'text-anchor':'middle',fill:colorText,'font-size':11}, label);
    });
    const iCurrent=data.findIndex(x=>x.month===current);
    if(iCurrent>=0 && iCurrent<12){
      const boundary=(X(iCurrent)+X(iCurrent+1))/2;
      add('rect',{x:boundary,y:T,width:W-R-boundary,height:plotH,fill:'var(--secondary-background-color)',opacity:'.65'});
      add('line',{x1:boundary,x2:boundary,y1:T,y2:T+plotH,stroke:'var(--secondary-text-color)','stroke-dasharray':'4 4'});
      add('text',{x:boundary+7,y:T+13,fill:colorText,'font-size':11},'výhled');
    }
    const draw=(field,color,dash)=>{
      const path=data.map((d,i)=>`${i?'L':'M'}${X(i).toFixed(1)},${Y(d[field]).toFixed(1)}`).join(' ');
      add('path',{d:path,fill:'none',stroke:color,'stroke-width':2.8,'stroke-linecap':'round',...(dash?{'stroke-dasharray':dash}:{})});
      data.forEach((d,i)=>add('circle',{cx:X(i),cy:Y(d[field]),r:3.2,fill:color}));
    };
    draw('advance','#d28b21','5 4'); draw('cost','#1683b0');
    svg.addEventListener('pointermove',e=>{
      const rect=svg.getBoundingClientRect(); const xv=(e.clientX-rect.left)/rect.width*W;
      const i=Math.max(0,Math.min(12,Math.round((xv-L)*12/plotW)));
      const d=data[i];
      info.textContent=`${d.month}: náklady a odhad ${d.cost.toLocaleString('cs-CZ',{style:'currency',currency:'CZK'})}; podle záloh ${d.advance.toLocaleString('cs-CZ',{style:'currency',currency:'CZK'})}`;
    });
    svg.addEventListener('pointerleave',()=>{info.textContent='';});
    graph.append(svg);
    info.textContent='Bod aktuálního měsíce může zahrnovat odhad innogy. Budoucí měsíce jsou prognóza, nikoli skutečná spotřeba.';
  }
}
if (!customElements.get('innosvet-cost-chart')) customElements.define('innosvet-cost-chart',InnosvetCostChart);
window.customCards = window.customCards || [];
if (!window.customCards.some(x => x.type === 'innosvet-cost-chart')) window.customCards.push({type:'innosvet-cost-chart',name:'innosvět · Vývoj nákladů',description:'Plyn a elektřina podle 13 měsíčních bodů portálu innosvět'});
