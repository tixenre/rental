/* ListView — split master/detail, smart chips, tabs, mobile cards */
const { Icon, EstadoBadge, StateDot, Btn, nextStep, RAMBLA } = window;
const { fmtARS, fechaCorta, fechaHora, breakdown, pagado, montoTotal, initials, sameDay, TODAY } = RAMBLA;

function cobranzaLabel(o){
  const pg = pagado(o), tot = montoTotal(o);
  if(o.estado==="borrador"||o.estado==="presupuesto") return null;
  if(pg>=tot && tot>0) return {cls:"full", tx:"pagado"};
  if(pg>0) return {cls:"part", tx:"seña "+fmtARS(pg)};
  return {cls:"none", tx:"sin seña"};
}

function MasterRow({o, sel, compact, showCob=true, onClick}){
  const cob = cobranzaLabel(o);
  const fechas = o.fecha_desde ? (fechaCorta(o.fecha_desde)+" → "+fechaCorta(o.fecha_hasta)) : "sin fechas";
  return (
    <div className={"mrow"+(sel?" sel":"")} onClick={onClick}>
      <div className="r1">
        <span className="cust">{o.cliente.nombre}</span>
        <EstadoBadge estado={o.estado}/>
      </div>
      <div className="r2">
        <span className="meta">
          {o.numero_pedido?("#"+String(o.numero_pedido).padStart(4,"0")):"manual"} · {o.retiraHoy?<b style={{color:"var(--amber)"}}>RETIRA HOY</b>:o.devuelveHoy?<b style={{color:"var(--rosa)"}}>DEVUELVE HOY</b>:fechas}
        </span>
        <span style={{display:"flex",alignItems:"center",gap:8}}>
          {o.tiene_solicitud_pendiente && <span className="modtag"><Icon name="pencil" size={9}/>mod.</span>}
          <span className="amt">{fmtARS(montoTotal(o))}</span>
        </span>
      </div>
      {!compact && showCob && cob && <div className={"cobr "+cob.cls} style={{marginTop:1}}>{cob.tx}</div>}
    </div>
  );
}

function PreviewPane({o, onOpen, onSetEstado, onPago, onWhatsApp, onEmail, onCollapse}){
  if(!o) return <div className="preview" style={{alignItems:"center",justifyContent:"center",color:"var(--muted-foreground)"}}><div style={{textAlign:"center"}}><Icon name="box" size={40} style={{opacity:.3}}/><div style={{marginTop:10,fontSize:14}}>Elegí un pedido de la izquierda</div></div></div>;
  const b = breakdown(o);
  const pg = pagado(o);
  const ns = nextStep(o);
  return (
    <div className="preview">
      <div className="pv-head">
        <div>
          <div style={{display:"flex",alignItems:"center",gap:10,flexWrap:"wrap"}}>
            <span className="nm">{o.cliente.nombre}</span>
            <EstadoBadge estado={o.estado}/>
            {o.tiene_solicitud_pendiente && <span className="modtag"><Icon name="pencil" size={9}/>modificación pendiente</span>}
          </div>
          <div className="sub">{o.numero_pedido?("Pedido #"+String(o.numero_pedido).padStart(4,"0")):"Registro manual"} · creado {o.createdAgo}{o.cliente.tipo?(" · "+o.cliente.tipo):""}</div>
        </div>
        <div style={{display:"flex",gap:8,flexShrink:0}}>
          <Btn variant="outline" size="sm" icon="pencil" onClick={()=>onOpen(o.id)}>Editar</Btn>
          <button className="iconbtn sm" title="Contraer detalle" onClick={onCollapse}><Icon name="panelLeft" size={15}/></button>
        </div>
      </div>

      {ns && (
        <div className="nextstep">
          <div className="ns-l">
            <div className="lbl">Siguiente paso</div>
            <div className="tx">{ns.label}</div>
          </div>
          <div style={{flex:1}}></div>
          {o.estado!=="finalizado" && o.estado!=="cancelado" && <Btn variant="ghost" size="sm" onClick={()=>onSetEstado(o.id,"cancelado")}>Cancelar</Btn>}
          <Btn variant={ns.blocked?"outline":"amber"} size="sm" pill icon={ns.icon} disabled={!!ns.blocked} title={ns.blocked||""} onClick={()=>onSetEstado(o.id,ns.target)}>{ns.blocked?("Falta: "+ns.blocked):ns.label}</Btn>
        </div>
      )}

      <div className="pv-grid">
        <div className="pv-cell">
          <div className="lbl">Fechas</div>
          <div className="med">{o.fecha_desde?(fechaCorta(o.fecha_desde)+" → "+fechaCorta(o.fecha_hasta)):"Sin fechas"}</div>
          <div className="muted" style={{fontSize:11,fontFamily:"var(--font-mono)",marginTop:3}}>{o.fecha_desde?(b.J+" jornada"+(b.J>1?"s":"")+" · stock OK ✓"):"definir para confirmar"}</div>
        </div>
        <div className="pv-cell">
          <div className="lbl">Total {b.conIva?"con IVA":"neto"}</div>
          <div className="big">{fmtARS(b.total)}</div>
          <div style={{fontSize:11,fontFamily:"var(--font-mono)",marginTop:3}} className={pg>=b.neto&&b.neto>0?"":"muted"}>
            {pg>=b.neto&&b.neto>0?<span style={{color:"var(--verde)"}}>pagado</span>:pg>0?("seña "+fmtARS(pg)+" · resta "+fmtARS(b.total-pg)):"sin seña registrada"}
          </div>
        </div>
      </div>

      <div className="items-box">
        <div className="ib-head"><span className="eyebrow">Equipos · {o.items.length}</span><span className="muted" style={{fontSize:10,fontFamily:"var(--font-mono)"}}>precio / jornada</span></div>
        {o.items.map((it,i)=>(
          <div className="it" key={i}>
            <div className="thumb"><Icon name="box" size={18}/></div>
            <div style={{flex:1,minWidth:0}}>
              <div className="inm">{it.nombre} {it.kit&&<span className="kitpill">kit · {it.componentes.length}</span>}</div>
              <div className="ime">{it.marca}{it.kit?(" · "+it.componentes.join(", ")):""}</div>
            </div>
            <div className="mono" style={{fontSize:12,color:"var(--muted-foreground)"}}>{it.cantidad}× {fmtARS(it.precio_jornada)}</div>
          </div>
        ))}
      </div>

      <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
        <Btn variant="wa" icon="whatsapp" onClick={()=>onWhatsApp(o)} disabled={!o.cliente.telefono}>WhatsApp</Btn>
        <Btn variant="outline" icon="mail" onClick={()=>onEmail(o)} disabled={!o.cliente.email}>Email</Btn>
        <Btn variant="outline" icon="coins" onClick={()=>onPago(o.id)}>Registrar pago</Btn>
        <Btn variant="outline" icon="file">Documentos</Btn>
      </div>
    </div>
  );
}

function ListView(props){
  const { orders, selectedId, onSelect, onOpen, tweaks, detailCollapsed, setDetailCollapsed, onSetEstado, onPago, onWhatsApp, onEmail, onNew } = props;
  const [tab, setTab] = React.useState("todos");
  const [smart, setSmart] = React.useState(null);
  const [estadoF, setEstadoF] = React.useState("activos");
  const [q, setQ] = React.useState("");

  const counts = React.useMemo(()=>({
    retiraHoy: orders.filter(o=>o.retiraHoy).length,
    devuelveHoy: orders.filter(o=>o.devuelveHoy).length,
    nuevos: orders.filter(o=>o.isNew).length,
    saldo: orders.filter(o=>["confirmado","retirado","devuelto","finalizado"].includes(o.estado)&&pagado(o)<montoTotal(o)).length,
    solicitudes: orders.filter(o=>o.tiene_solicitud_pendiente).length,
    activos: orders.filter(o=>o.estado!=="finalizado"&&o.estado!=="cancelado").length,
  }),[orders]);

  const filtered = React.useMemo(()=>{
    let r = orders.slice();
    if(tab==="cobranzas") r = r.filter(o=>["confirmado","retirado","devuelto","finalizado"].includes(o.estado)&&pagado(o)<montoTotal(o));
    else if(tab==="solicitudes") r = r.filter(o=>o.tiene_solicitud_pendiente);
    if(smart==="retiraHoy") r=r.filter(o=>o.retiraHoy);
    else if(smart==="devuelveHoy") r=r.filter(o=>o.devuelveHoy);
    else if(smart==="nuevos") r=r.filter(o=>o.isNew);
    else if(smart==="saldo") r=r.filter(o=>["confirmado","retirado","devuelto","finalizado"].includes(o.estado)&&pagado(o)<montoTotal(o));
    if(tab==="todos" && !smart){
      if(estadoF==="activos") r=r.filter(o=>o.estado!=="finalizado"&&o.estado!=="cancelado");
      else if(estadoF==="presupuesto") r=r.filter(o=>o.estado==="presupuesto"||o.estado==="borrador");
      else if(estadoF==="confirmado") r=r.filter(o=>o.estado==="confirmado");
      else if(estadoF==="cerrados") r=r.filter(o=>o.estado==="finalizado"||o.estado==="cancelado");
    }
    if(q.trim()){ const s=q.toLowerCase(); r=r.filter(o=>o.cliente.nombre.toLowerCase().includes(s)||String(o.numero_pedido||"").includes(s)); }
    // orden: número desc, manual al final
    r.sort((a,b)=>(b.numero_pedido?1:0)-(a.numero_pedido?1:0)|| (b.numero_pedido||0)-(a.numero_pedido||0));
    return r;
  },[orders,tab,smart,estadoF,q]);

  const sel = orders.find(o=>o.id===selectedId);
  const detailOpen = tweaks.preview && !detailCollapsed;
  const splitCls = ["split"];
  if(!detailOpen) splitCls.push("nopreview");
  if(tweaks.density==="compact") splitCls.push("compact");
  const openRow = (id)=>{ if(tweaks.preview){ onSelect(id); setDetailCollapsed(false);} else onOpen(id); };

  const SmartChip = ({id, color, label, n}) => (
    <button className={"chip smart"+(smart===id?" on":"")} onClick={()=>setSmart(smart===id?null:id)}>
      <span className="sdot" style={{background:color}}></span>{label}{n>0&&<span className="cnt">{n}</span>}
    </button>
  );

  return (
    <>
      <div className="list-head">
        <div className="list-toprow">
          <div>
            <div className="eyebrow">Operaciones · Pedidos</div>
            <div style={{display:"flex",alignItems:"baseline",gap:10}}>
              <h1 style={{fontSize:26,fontWeight:700,letterSpacing:"-.01em"}}>Pedidos</h1>
            </div>
            <div className="sub hide-mobile">Reservas activas y solicitudes de cambio de tus clientes. {orders.length} en total.</div>
          </div>
          <div style={{flex:1}}></div>
          <Btn variant="outline" icon="file" className="hide-mobile" onClick={onNew}>Presupuesto</Btn>
          <Btn variant="ink" icon="plus" onClick={onNew}>Nuevo pedido</Btn>
        </div>

        <div className="tabbar">
          {[["todos","Todos"],["cobranzas","Cobranzas"],["solicitudes","Solicitudes"]].map(([id,l])=>(
            <button key={id} className={"tab"+(tab===id?" on":"")} onClick={()=>{setTab(id);setSmart(null);}}>
              {id==="cobranzas"&&<Icon name="coins" size={14}/>}{l}
              {id==="solicitudes"&&counts.solicitudes>0&&<span className="nb">{counts.solicitudes}</span>}
            </button>
          ))}
        </div>

        {tab!=="solicitudes" && (
          <div className="chips-scroll">
            <SmartChip id="retiraHoy" color="var(--amber)" label="Retiran hoy" n={counts.retiraHoy}/>
            <SmartChip id="devuelveHoy" color="var(--rosa)" label="Devuelven hoy" n={counts.devuelveHoy}/>
            <SmartChip id="nuevos" color="var(--azul)" label="Presupuestos nuevos" n={counts.nuevos}/>
            <SmartChip id="saldo" color="var(--verde)" label="Con saldo" n={counts.saldo}/>
          </div>
        )}

        <div style={{display:"flex",gap:10,alignItems:"center",flexWrap:"wrap"}}>
          <div className="searchwrap" style={{flex:1,maxWidth:360,minWidth:180}}>
            <Icon name="search" size={15}/>
            <input value={q} onChange={e=>setQ(e.target.value)} placeholder="Buscar cliente o número…"/>
          </div>
          <div style={{flex:1}}></div>
          {tab==="todos" && !smart && (
            <div className="chips-row hide-mobile">
              {[["activos","Activos"],["presupuesto","Solicitados"],["confirmado","Confirmados"],["cerrados","Cerrados"],["todos","Todos"]].map(([id,l])=>(
                <button key={id} className={"chip"+(estadoF===id?" on":"")} onClick={()=>setEstadoF(id)}>{l}{id==="activos"&&<span className="cnt">{counts.activos}</span>}</button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className={splitCls.join(" ")}>
        {/* desktop master list (340px) — only when detail panel open */}
        {detailOpen && (
          <div className="masterwrap">
            <div className="master-list">
              {filtered.map(o=><MasterRow key={o.id} o={o} sel={o.id===selectedId} compact={tweaks.density==="compact"} showCob={tweaks.showCobranza} onClick={()=>onSelect(o.id)}/>)}
              {!filtered.length&&<div style={{padding:30,textAlign:"center",color:"var(--muted-foreground)",fontSize:13}}>Sin pedidos.</div>}
            </div>
          </div>
        )}

        {detailOpen
          ? <PreviewPane o={sel} onOpen={onOpen} onSetEstado={onSetEstado} onPago={onPago} onWhatsApp={onWhatsApp} onEmail={onEmail} onCollapse={()=>setDetailCollapsed(true)}/>
          : <div className="master-list" style={{overflowY:"auto"}}>
              {tweaks.preview && (
                <div className="master-top" style={{position:"sticky",top:0,background:"var(--surface-elevated)",zIndex:2}}>
                  <span className="eyebrow" style={{whiteSpace:"nowrap"}}>{filtered.length} pedido{filtered.length!==1?"s":""}</span>
                  <div style={{flex:1}}></div>
                  <button className="iconbtn sm" title="Mostrar detalle" onClick={()=>setDetailCollapsed(false)}><Icon name="panelLeft" size={15}/></button>
                </div>
              )}
              {filtered.map(o=><MasterRow key={o.id} o={o} sel={tweaks.preview&&o.id===selectedId} compact={tweaks.density==="compact"} showCob={tweaks.showCobranza} onClick={()=>openRow(o.id)}/>)}
              {!filtered.length&&<div style={{padding:30,textAlign:"center",color:"var(--muted-foreground)",fontSize:13}}>Sin pedidos.</div>}
            </div>
        }

        {/* mobile cards */}
        <div className="mcards">
          {filtered.map(o=>{
            const ns = nextStep(o);
            return (
              <div className="mcard" key={o.id} onClick={()=>onOpen(o.id)}>
                <div className="mc-r1"><span className="mc-num">{o.numero_pedido?("#"+String(o.numero_pedido).padStart(4,"0")):"manual"}</span><EstadoBadge estado={o.estado}/></div>
                <div>
                  <div className="mc-cust">{o.cliente.nombre}</div>
                  <div className="mc-meta">{o.retiraHoy?<b style={{color:"var(--amber)"}}>RETIRA HOY {fechaHora(o.fecha_desde).split("·")[1]||""}</b>:o.devuelveHoy?<b style={{color:"var(--rosa)"}}>DEVUELVE HOY</b>:(o.fecha_desde?(fechaCorta(o.fecha_desde)+" → "+fechaCorta(o.fecha_hasta)):"sin fechas")} · {o.items.length} eq</div>
                </div>
                <div className="mc-foot">
                  <div><span className="mono" style={{fontWeight:600}}>{fmtARS(montoTotal(o))}</span> {(()=>{const c=cobranzaLabel(o);return c?<span className={"cobr "+c.cls} style={{marginLeft:4}}>{c.tx}</span>:null;})()}</div>
                  <div style={{display:"flex",gap:7}} onClick={e=>e.stopPropagation()}>
                    {o.cliente.telefono&&<button className="iconbtn sm wa" onClick={()=>onWhatsApp(o)}><Icon name="whatsapp" size={15}/></button>}
                    {ns&&!ns.blocked&&(o.retiraHoy||o.devuelveHoy)
                      ? <Btn variant="amber" size="sm" pill onClick={()=>onSetEstado(o.id,ns.target)}>{ns.target==="retirado"?"Entregar":"Recibir"}</Btn>
                      : <button className="iconbtn sm"><Icon name="chevronR" size={15}/></button>}
                  </div>
                </div>
              </div>
            );
          })}
          {!filtered.length&&<div style={{padding:30,textAlign:"center",color:"var(--muted-foreground)",fontSize:13}}>Sin pedidos.</div>}
        </div>
      </div>

      <button className="fab" onClick={onNew} title="Nuevo pedido"><Icon name="plus" size={24} sw={2.5}/></button>
    </>
  );
}
window.ListView = ListView;
