/* EditorView — 2-col work surface */
const { Icon, EstadoBadge, Btn, Stepper, Field, nextStep, transitions, blockReason, ESTADOS, FLOW, RAMBLA } = window;
const { fmtARS, fechaHora, fechaCorta, breakdown, pagado, CATALOGO } = RAMBLA;

function EstadoDropdown({o, onSetEstado}){
  const [open,setOpen] = React.useState(false);
  const ref = React.useRef();
  React.useEffect(()=>{
    const h=(e)=>{ if(ref.current&&!ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown",h); return ()=>document.removeEventListener("mousedown",h);
  },[]);
  const valid = transitions(o);
  const all = ["presupuesto","confirmado","retirado","devuelto","finalizado","cancelado"];
  return (
    <div className="dd" ref={ref}>
      <button className="dd-btn" onClick={()=>setOpen(!open)}>
        <span className="sdot" style={{background:window.dotColor(o.estado)}}></span>
        {ESTADOS[o.estado].label}
        <span style={{flex:1}}></span>
        <Icon name="chevronD" size={14}/>
      </button>
      {open && (
        <div className="dd-menu">
          {all.map(e=>{
            const isCur = e===o.estado;
            const allowed = isCur || valid.includes(e);
            const reason = allowed && !isCur ? blockReason(o,e) : null;
            const dis = !allowed || !!reason;
            return (
              <div key={e} className={"dd-opt"+(isCur?" cur":"")+(dis?" dis":"")}
                onClick={()=>{ if(!dis&&!isCur){ onSetEstado(o.id,e); setOpen(false);} }}>
                <span className="sdot" style={{background:window.dotColor(e)}}></span>
                {ESTADOS[e].label}
                {isCur && <Icon name="check" size={14} style={{marginLeft:"auto",color:"var(--verde)"}}/>}
                {reason && <span className="why">{reason}</span>}
                {!allowed && !isCur && <Icon name="lock" size={12} style={{marginLeft:"auto",color:"var(--muted-foreground)"}}/>}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function FlowStrip({estado}){
  const idx = FLOW.indexOf(estado);
  if(estado==="cancelado") return <div className="flow"><span className="fs cur est-cancelado" style={{borderColor:"var(--destructive)"}}><span className="sdot" style={{background:"var(--destructive)"}}></span>Cancelado</span></div>;
  return (
    <div className="flow">
      {FLOW.map((e,i)=>(
        <React.Fragment key={e}>
          <span className={"fs"+(i<idx?" done":"")+(i===idx?" cur":"")}><span className="sdot" style={{background:window.dotColor(e)}}></span>{ESTADOS[e].label.slice(0,6)}{ESTADOS[e].label.length>6?".":""}</span>
          {i<FLOW.length-1 && <span className="fa">›</span>}
        </React.Fragment>
      ))}
    </div>
  );
}

function AddEquipo({onAdd, existing}){
  const [q,setQ] = React.useState("");
  const [open,setOpen] = React.useState(false);
  const ref = React.useRef();
  React.useEffect(()=>{ const h=(e)=>{ if(ref.current&&!ref.current.contains(e.target)) setOpen(false); }; document.addEventListener("mousedown",h); return ()=>document.removeEventListener("mousedown",h); },[]);
  const res = CATALOGO.filter(c=>!existing.includes(c.id) && (c.nombre.toLowerCase().includes(q.toLowerCase())||c.marca.toLowerCase().includes(q.toLowerCase()))).slice(0,6);
  return (
    <div className="addbox" ref={ref}>
      <div className="inp search" style={{borderStyle:"dashed"}} onClick={()=>setOpen(true)}>
        <Icon name="search" size={14} style={{color:"var(--muted-foreground)"}}/>
        <input value={q} onChange={e=>{setQ(e.target.value);setOpen(true);}} onFocus={()=>setOpen(true)} placeholder="Buscar y agregar equipo…"/>
      </div>
      {open && res.length>0 && (
        <div className="addresults">
          {res.map(c=>(
            <div className="addres" key={c.id} onClick={()=>{onAdd(c);setQ("");setOpen(false);}}>
              <div className="thumb" style={{width:34,height:34}}><Icon name="box" size={16}/></div>
              <div style={{flex:1}}><div style={{fontSize:13,fontWeight:700,color:"var(--ink)"}}>{c.nombre}</div><div className="mono muted" style={{fontSize:10}}>{c.marca} · stock {c.stock}</div></div>
              <span className="mono" style={{fontSize:12,color:"var(--muted-foreground)"}}>{fmtARS(c.precio_jornada)}</span>
              <Icon name="plus" size={16} style={{color:"var(--amber)"}}/>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function EditorView(props){
  const { o, onSetEstado, onPatch, onAddItem, onRemoveItem, onQty, onPago, onWhatsApp, onEmail, onResolveSolicitud } = props;
  if(!o) return null;
  const b = breakdown(o);
  const pg = pagado(o);
  const ns = nextStep(o);
  const existing = o.items.map(i=>i.equipo_id);

  const Rail = (
    <>
      <div className="rail-sec">
        <div className="rail-lbl">Estado del pedido</div>
        <EstadoDropdown o={o} onSetEstado={onSetEstado}/>
        <FlowStrip estado={o.estado}/>
        {ns && <Btn variant={ns.blocked?"outline":"ink"} pill block icon={ns.icon} disabled={!!ns.blocked} title={ns.blocked||""} onClick={()=>onSetEstado(o.id,ns.target)}>{ns.blocked?("Falta: "+ns.blocked):ns.label}</Btn>}
      </div>
      <hr className="hr"/>
      <div className="rail-sec">
        <div className="rail-lbl">Desglose · lo calcula el backend</div>
        <div className="bd">
          <div className="bd-r"><span className="l">Bruto · {b.J} jornada{b.J>1?"s":""}</span><span className="v">{fmtARS(b.bruto)}</span></div>
          {o.descuento_pct>0 && <div className="bd-r"><span className="l">Descuento {o.descuento_pct}%</span><span className="v neg">– {fmtARS(b.desc)}</span></div>}
          <div className="bd-r"><span className="l">Neto</span><span className="v">{fmtARS(b.neto)}</span></div>
          <div className="bd-r"><span className="l">IVA {b.conIva?"21%":""}</span><span className="v">{b.conIva?fmtARS(b.iva):"— cons. final"}</span></div>
          <div className="bd-div"></div>
          <div className="bd-tot"><span className="l">Total</span><span className="v">{fmtARS(b.total)}</span></div>
        </div>
        <Field label="Descuento manual %">
          <div className="inp" style={{maxWidth:120}}><input type="number" value={o.descuento_pct} min={0} max={100} onChange={e=>onPatch(o.id,{descuento_pct:Math.max(0,Math.min(100,Number(e.target.value)||0))})}/><span className="muted">%</span></div>
        </Field>
      </div>
      <hr className="hr"/>
      <div className="rail-sec">
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}><span className="rail-lbl">Cobranza</span><span className="mono" style={{fontSize:11,color:pg>=b.total?"var(--verde)":"var(--destructive)"}}>{pg>=b.total&&b.total>0?"pagado":("resta "+fmtARS(b.total-pg))}</span></div>
        <div className="prog"><i style={{width:(b.total?Math.min(100,pg/b.total*100):0)+"%"}}></i></div>
        <div className="muted" style={{fontSize:11,fontFamily:"var(--font-mono)"}}>{fmtARS(pg)} de {fmtARS(b.total)}{pg===0?" · sin seña":""}</div>
        {(o.pagos||[]).map((p,i)=>(<div key={i} style={{display:"flex",justifyContent:"space-between",fontSize:12}}><span className="muted">{p.concepto||"Pago"} · {p.fecha}</span><span className="mono">{fmtARS(p.monto)}</span></div>))}
        <Btn variant="outline" size="sm" block icon="plus" disabled={o.estado==="cancelado"} onClick={()=>onPago(o.id)}>Registrar pago</Btn>
      </div>
      <hr className="hr"/>
      <div className="rail-sec">
        <div className="rail-lbl">Documentos</div>
        <div className="docs">
          {["Remito","Contrato","Packing","Presupuesto"].map(d=><span className="docchip" key={d}><Icon name="file" size={12}/>{d}</span>)}
        </div>
        <Btn variant="danger" size="sm" block icon="trash" style={{marginTop:4}}>Eliminar pedido</Btn>
      </div>
    </>
  );

  return (
    <div className="editor">
      <div className="ed-main">
        <div className="ed-main-inner">
          {o.solicitud && (
            <div className="modbanner">
              <span className="mb-ic"><Icon name="pencil" size={18}/></span>
              <div style={{flex:1}}>
                <div className="mb-t">El cliente pidió un cambio {o.solicitud.tipo==="fechas"?"de fechas":""}</div>
                <div className="muted" style={{fontSize:12,marginTop:2,fontStyle:"italic"}}>“{o.solicitud.mensaje}”</div>
                <div className="diffrow"><span className="was">{o.solicitud.was}</span><Icon name="arrowR" size={13} style={{color:"var(--azul)"}}/><span className="now">{o.solicitud.now}</span></div>
                <div style={{display:"flex",gap:7,marginTop:9,flexWrap:"wrap"}}>
                  <Btn variant="ink" size="sm" onClick={()=>onResolveSolicitud(o.id,"aprobar")}>Aprobar</Btn>
                  <Btn variant="outline" size="sm" onClick={()=>onResolveSolicitud(o.id,"contra")}>Contraproponer</Btn>
                  <Btn variant="ghost" size="sm" onClick={()=>onResolveSolicitud(o.id,"rechazar")}>Rechazar</Btn>
                </div>
              </div>
            </div>
          )}

          {/* Cliente */}
          <div className="sec">
            <div className="sec-h"><Icon name="user" size={15}/><span className="ttl">Cliente</span><span style={{flex:1}}></span><Btn variant="ghost" size="sm" onClick={()=>{}}>Cambiar</Btn></div>
            <div className="sec-b">
              <div className="frow">
                <Field label="Nombre"><div className="inp"><input value={o.cliente.nombre} onChange={e=>onPatch(o.id,{cliente:{...o.cliente,nombre:e.target.value}})}/></div></Field>
                <Field label="Teléfono"><div className="inp"><input value={o.cliente.telefono} onChange={e=>onPatch(o.id,{cliente:{...o.cliente,telefono:e.target.value}})}/></div></Field>
              </div>
              <div className="frow">
                <Field label="Email" style={{flex:2}}><div className="inp"><input value={o.cliente.email} placeholder="—" onChange={e=>onPatch(o.id,{cliente:{...o.cliente,email:e.target.value}})}/></div></Field>
                <Field label="Perfil de IVA"><div className="inp">{o.cliente.perfil==="responsable_inscripto"?"Resp. inscripto":"Consumidor final"}</div></Field>
              </div>
            </div>
          </div>

          {/* Fechas */}
          <div className="sec">
            <div className="sec-h"><Icon name="calendar" size={15}/><span className="ttl">Fechas del alquiler</span><span style={{flex:1}}></span>
              {o.fecha_desde
                ? <span className="availtag ok"><Icon name="check" size={11}/>stock OK</span>
                : <span className="availtag no"><Icon name="alert" size={11}/>sin fechas</span>}
            </div>
            <div className="sec-b">
              <div className="frow" style={{alignItems:"flex-end"}}>
                <Field label="Retiro"><div className="inp"><Icon name="calendar" size={14} style={{color:"var(--muted-foreground)"}}/>{o.fecha_desde?fechaHora(o.fecha_desde):"definir"}</div></Field>
                <Field label="Devolución"><div className="inp"><Icon name="calendar" size={14} style={{color:"var(--muted-foreground)"}}/>{o.fecha_hasta?fechaHora(o.fecha_hasta):"definir"}</div></Field>
                <div className="card" style={{padding:"8px 14px",textAlign:"center",flexShrink:0}}><div className="mono" style={{fontSize:20,fontWeight:600,lineHeight:1}}>{b.J}</div><div className="eyebrow" style={{fontSize:8}}>jornadas</div></div>
              </div>
              <div className="muted" style={{fontSize:11,fontFamily:"var(--font-mono)"}}>Cambiar fechas re-valida disponibilidad contra las reservas reales.</div>
            </div>
          </div>

          {/* Equipos */}
          <div className="sec">
            <div className="sec-h"><Icon name="box" size={15}/><span className="ttl">Equipos · {o.items.length}</span></div>
            <div className="sec-b">
              <AddEquipo onAdd={(c)=>onAddItem(o.id,c)} existing={existing}/>
              {o.items.map((it,i)=>(
                <div className="it" key={it.equipo_id} style={{paddingLeft:0,paddingRight:0}}>
                  <div className="thumb"><Icon name="box" size={18}/></div>
                  <div style={{flex:1,minWidth:0}}>
                    <div className="inm">{it.nombre} {it.kit&&<span className="kitpill">kit · {it.componentes.length}</span>}</div>
                    <div className="ime">{fmtARS(it.precio_jornada)} / jornada{it.kit?(" · "+it.componentes.join(", ")):""}</div>
                  </div>
                  <Stepper value={it.cantidad} min={1} max={99} onChange={(v)=>onQty(o.id,it.equipo_id,v)}/>
                  <div className="mono" style={{fontWeight:600,width:84,textAlign:"right",fontSize:13}}>{fmtARS(it.precio_jornada*it.cantidad*b.J)}</div>
                  <button className="iconbtn sm ghost" onClick={()=>onRemoveItem(o.id,it.equipo_id)}><Icon name="trash" size={14} style={{color:"var(--destructive)"}}/></button>
                </div>
              ))}
              {!o.items.length && <div className="muted" style={{fontSize:13,padding:"6px 0"}}>Sin equipos. Agregá al menos uno para confirmar.</div>}
            </div>
          </div>

          {/* Notas */}
          <div className="sec">
            <div className="sec-h"><Icon name="file" size={15}/><span className="ttl">Notas internas</span></div>
            <div className="sec-b">
              <textarea className="inp" value={o.notas} placeholder="Notas para el equipo de Rambla…" onChange={e=>onPatch(o.id,{notas:e.target.value})}/>
            </div>
          </div>
        </div>
      </div>

      <div className="ed-rail">{Rail}</div>

      {/* mobile sticky bottom bar */}
      <div className="botbar show-mobile">
        <div className="bt-tot"><div className="l">Total</div><div className="v">{fmtARS(b.total)}</div></div>
        <span className="saved"><Icon name="check" size={12}/>Guardado</span>
        <div style={{flex:1}}></div>
        {o.cliente.email&&<button className="iconbtn" title="Enviar email" onClick={()=>onEmail(o)}><Icon name="mail" size={16}/></button>}
        {o.cliente.telefono&&<button className="iconbtn wa" onClick={()=>onWhatsApp(o)}><Icon name="whatsapp" size={16}/></button>}
        {ns&&<Btn variant={ns.blocked?"outline":"amber"} pill icon={ns.icon} disabled={!!ns.blocked} onClick={()=>onSetEstado(o.id,ns.target)}>{ns.blocked?ns.blocked:ns.label.split(" ")[0]}</Btn>}
      </div>
    </div>
  );
}
window.EditorView = EditorView;
