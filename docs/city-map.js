/* Complete isometric city. SVG keeps sectors and every building interactive
   without a GPU, a CDN, or a network renderer. Geometry is registry-derived. */
(function (root) {
  'use strict';
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const project = (x, z, h = 0) => [(x - z) * .866, (x + z) * .5 - h];
  const pts = points => points.map(p => p.map(n => +n.toFixed(2)).join(',')).join(' ');
  function box(x, z, width, height) {
    const r = width / 2;
    return {
      top: [project(x-r,z-r,height),project(x+r,z-r,height),project(x+r,z+r,height),project(x-r,z+r,height)],
      left: [project(x-r,z+r,height),project(x+r,z+r,height),project(x+r,z+r),project(x-r,z+r)],
      right: [project(x+r,z-r,height),project(x+r,z+r,height),project(x+r,z+r),project(x+r,z-r)]
    };
  }
  function bounds(data, zone) {
    const points = [];
    for (const d of data.districts.filter(d => !zone || d.id === zone)) {
      const b = box(d.cx,d.cz,82,0); points.push(...b.top);
    }
    for (const b of data.bots.filter(b => !zone || b.zone === zone)) points.push(...box(b.x,b.z,b.w,Math.min(b.h*.5,32)).top);
    const xs=points.map(p=>p[0]), ys=points.map(p=>p[1]);
    const x=Math.min(...xs)-18, y=Math.min(...ys)-24;
    return [x,y,Math.max(...xs)-x+18,Math.max(...ys)-y+28];
  }
  function render(data, zone = '', selected = null) {
    const focus = data.districts.find(d=>d.id===zone);
    const districts = data.districts.filter(d=>!focus || d.id===zone).sort((a,b)=>(a.cx+a.cz)-(b.cx+b.cz));
    const plots = districts.map(d=>{
      const ground=box(d.cx,d.cz,75,1), label=project(d.cx,d.cz+40);
      return '<g class="iso-sector" data-zone="'+esc(d.id)+'" role="button" tabindex="0" aria-label="'+esc(d.label)+', '+d.count+' bots"><title>'+esc(d.label)+' · '+d.count+' bots</title><polygon class="iso-ground" points="'+pts(ground.top)+'" fill="'+d.color+'" fill-opacity=".1" stroke="'+d.color+'" stroke-opacity=".5" stroke-width=".5"/><polygon points="'+pts(ground.left)+'" fill="#101f30"/><polygon points="'+pts(ground.right)+'" fill="#0a1521"/><text class="sector-sign" x="'+label[0]+'" y="'+(label[1]+5)+'" text-anchor="middle" fill="'+d.color+'">'+esc(d.label)+'</text><text class="sector-pop" x="'+label[0]+'" y="'+(label[1]+10)+'" text-anchor="middle">'+d.count+' BOTS</text></g>';
    }).join('');
    const buildings = data.bots.filter(b=>!focus||b.zone===zone).sort((a,b)=>(a.x+a.z)-(b.x+b.z)||a.i-b.i).map(b=>{
      const d=data.districts.find(d=>d.id===b.zone), h=Math.min(b.h*.5,32), g=box(b.x,b.z,b.w,h);
      const color=b.pnl===null?d.color:b.pnl>=0?'#65e4ad':'#f87886';
      let windows='';
      // Facade lights, with stable density tied to the actual role building.
      for(let y=2;y<h-1;y+=3) {
        const l=project(b.x,b.z+b.w/2,y),r=project(b.x+b.w/2,b.z,y);
        windows+='<path d="M'+l[0]+' '+l[1]+'l'+(b.w*.26)+' '+(b.w*.15)+'M'+r[0]+' '+r[1]+'l-'+(b.w*.26)+' '+(b.w*.15)+'" stroke="'+color+'" stroke-width=".55" opacity=".65"/>';
      }
      return '<g class="iso-building'+(selected===b.i?' selected':'')+'" data-zone="'+esc(b.zone)+'" data-bot="'+b.i+'"'+(focus?' role="button" tabindex="0"':'')+' aria-label="'+esc(b.name)+'"><title>'+esc(b.name)+' · '+esc(b.kind)+'</title><polygon points="'+pts(g.left)+'" fill="#173244" stroke="'+color+'" stroke-opacity=".25" stroke-width=".25"/><polygon points="'+pts(g.right)+'" fill="#0e2233" stroke="'+color+'" stroke-opacity=".3" stroke-width=".25"/>'+windows+'<polygon class="iso-roof" points="'+pts(g.top)+'" fill="'+color+'" fill-opacity=".7" stroke="'+color+'" stroke-width=".35"/></g>';
    }).join('');
    // Labels sit above the buildings with generous hit targets.
    const signs=districts.map(d=>{
      const p=project(d.cx,d.cz-40,12), label=esc(d.label);
      return '<g class="iso-sign" data-zone="'+esc(d.id)+'" role="button" tabindex="0" aria-label="Open '+label+'"><rect x="'+(p[0]-Math.max(18,d.label.length*1.3))+'" y="'+(p[1]-6)+'" width="'+Math.max(36,d.label.length*2.6)+'" height="10" rx="1.5" fill="#0b1725" stroke="'+d.color+'" stroke-width=".35"/><text x="'+p[0]+'" y="'+p[1]+'" text-anchor="middle" fill="'+d.color+'">'+label+'</text></g>';
    }).join('');
    return '<svg viewBox="'+bounds(data,zone).join(' ')+'" role="group" aria-label="Isometric city: '+data.bots.length+' bots across '+data.districts.length+' sectors"><defs><radialGradient id="city-glow"><stop stop-color="#152b42"/><stop offset="1" stop-color="#070e18"/></radialGradient><pattern id="roads" width="15" height="15" patternUnits="userSpaceOnUse" patternTransform="matrix(.866 .5 -.866 .5 0 0)"><path d="M0 0H15V15" fill="none" stroke="#1e3449" stroke-width=".35"/></pattern></defs><rect x="-600" y="-600" width="1200" height="1200" fill="url(#city-glow)"/><rect x="-500" y="-500" width="1000" height="1000" fill="url(#roads)"/>'+plots+buildings+signs+'</svg>';
  }
  const api={project,box,bounds,render};
  if(typeof module==='object'&&module.exports)module.exports=api;
  root.CityMap=api;
})(typeof globalThis==='object'?globalThis:this);
