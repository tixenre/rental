/* App — state, routing list⇄editor, topbar, drawer, pago modal, toasts, tweaks */
const { Icon, EstadoBadge, Btn, Field, ListView, EditorView, CommsModal, blockReason, ESTADOS, nextStep, RAMBLA } = window;
const { fmtARS, breakdown, pagado, montoTotal } = RAMBLA;
const { useTweaks, TweaksPanel, TweakSection, TweakRadio, TweakToggle } = window;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "density": "cómoda",
  "preview": true,
  "showCobranza": true,
  "dark": false
}/*EDITMODE-END*/;

function PagoModal({o, onClose, onSave}){
  const b = breakdown(o); const pg = pagado(o); const saldo = Math.max(0,b.total-pg);
  const [monto,setMonto] = React.useState(saldo);
  const [concepto,setConcepto] = React.useState(pg===0?"Seña":"Saldo");
  const presets = [["Seña 50%",Math.round(b.total*0.5)],["Saldo total",saldo],["Otro",null]];
  return (
    <div className="scrim" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}>
      <div className="modal">
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
          <h3>Registrar pago</h3>
          <button className="iconbtn sm ghost" onClick={onClose}><Icon name="x" size={16}/></button>
        </div>
        <div className="prog"><i style={{width:(b.total?Math.min(100,pg/b.total*100):0)+"%"}}></i></div>
        <div className="muted" style={{fontSize:12,fontFamily:"var(--font-mono)"}}>{fmtARS(pg)} de {fmtARS(b.total)} · resta {fmtARS(saldo)}</div>
        <div className="segrow">
          {presets.map(([l,v])=>(
            <button key={l} className={"chip"+(v===monto||(v===null&&![Math.round(b.total*0.5),saldo].includes(monto))?" on":"")} onClick={()=>{if(v!=null)setMonto(v); setConcepto(l.includes("Seña")?"Seña":l.includes("Saldo")?"Saldo final":"Pago");}}>{l}</button>
          ))}
        </div>
        <Field label="Monto">
          <div className="inp" style={{height:48}}><span className="mono muted">$</span><input type="number" value={monto} onChange={e=>setMonto(Math.max(0,Number(e.target.value)||0))} style={{fontSize:22,fontWeight:600,fontFamily:"var(--font-mono)"}}/></div>
        </Field>
        <div className="frow">
          <Field label="Concepto" style={{flex:1}}><div className="inp"><input value={concepto} onChange={e=>setConcepto(e.target.value)}/></div></Field>
          <Field label="Fecha"><div className="inp"><input value="hoy · 1 jun" readOnly/></div></Field>
        </div>
        {monto>=saldo && saldo>0 && o.estado==="devuelto" && <div className="availtag ok" style={{alignSelf:"flex-start"}}><Icon name="check" size={11}/>cubre el saldo → finaliza el pedido</div>}
        <Btn variant="amber" pill block onClick={()=>onSave(o.id,monto,concepto)}>Cobrar {fmtARS(monto)}</Btn>
      </div>
    </div>
  );
}

function App(){
  const [t,setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [orders,setOrders] = React.useState(()=>RAMBLA.orders.map(o=>({...o})));
  const [view,setView] = React.useState("list");
  const [selectedId,setSelectedId] = React.useState(RAMBLA.orders[0].id);
  const [detailCollapsed,setDetailCollapsed] = React.useState(false);
  const [drawer,setDrawer] = React.useState(false);
  const [modal,setModal] = React.useState(null);
  const [comms,setComms] = React.useState(null);
  const [toast,setToast] = React.useState(null);

  React.useEffect(()=>{ document.documentElement.classList.toggle("dark", !!t.dark); },[t.dark]);
  const flash = (msg,kind)=>{ setToast({msg,kind}); clearTimeout(window.__tt); window.__tt=setTimeout(()=>setToast(null),2600); };

  const upd = (id,fn)=> setOrders(os=>os.map(o=>{ if(o.id!==id) return o; const n=fn({...o}); n.tiene_solicitud_pendiente=!!n.solicitud; return n; }));

  const setEstado = (id,estado)=>{
    const o = orders.find(x=>x.id===id);
    const reason = blockReason(o,estado);
    if(reason){ flash("No se puede pasar a "+ESTADOS[estado].label+": "+reason,"err"); return; }
    upd(id,o=>{
      o.estado=estado;
      if(estado==="confirmado"&&!o.numero_pedido) o.numero_pedido=o.id;
      // auto-finalizar si devuelto y saldo 0
      if(estado==="devuelto" && pagado(o)>=montoTotal(o) && montoTotal(o)>0) o.estado="finalizado";
      o.retiraHoy=o.estado==="confirmado"&&RAMBLA.sameDay(o.fecha_desde,RAMBLA.TODAY);
      o.devuelveHoy=o.estado==="retirado"&&RAMBLA.sameDay(o.fecha_hasta,RAMBLA.TODAY);
      return o;
    });
    flash("Estado → "+ESTADOS[estado].label, "ok");
  };
  const patch = (id,p)=> upd(id,o=>Object.assign(o,p));
  const addItem = (id,c)=> upd(id,o=>{ o.items=[...o.items,{equipo_id:c.id,nombre:c.nombre,marca:c.marca,precio_jornada:c.precio_jornada,cantidad:1,kit:c.kit,componentes:c.componentes}]; return o; });
  const removeItem = (id,eid)=> upd(id,o=>{ o.items=o.items.filter(i=>i.equipo_id!==eid); return o; });
  const setQty = (id,eid,q)=> upd(id,o=>{ o.items=o.items.map(i=>i.equipo_id===eid?{...i,cantidad:q}:i); return o; });
  const savePago = (id,monto,concepto)=>{
    upd(id,o=>{
      o.pagos=[...(o.pagos||[]),{monto,concepto,fecha:"2026-06-01"}];
      if(o.estado==="devuelto" && pagado(o)>=montoTotal(o)) o.estado="finalizado";
      return o;
    });
    setModal(null); flash("Pago registrado: "+fmtARS(monto),"ok");
  };
  const resolveSolicitud = (id,action)=>{
    upd(id,o=>{
      if(action==="aprobar" && o.solicitud && o.solicitud.tipo==="fechas"){
        // aplica nueva fecha_hasta (demo: +2 días)
        if(o.fecha_hasta){ const nd=new Date(o.fecha_hasta); nd.setDate(nd.getDate()+2); o.fecha_hasta=nd; }
      }
      o.solicitud=null; return o;
    });
    flash(action==="aprobar"?"Cambio aprobado y aplicado":action==="rechazar"?"Solicitud rechazada":"Contrapropuesta enviada","ok");
  };
  const whatsapp = (o)=> setComms({channel:"wa",id:o.id});
  const email = (o)=> setComms({channel:"mail",id:o.id});
  const sendComms = (channel,key,attach)=>{ setComms(null); flash(channel==="mail"?("Email enviado al cliente"+(attach&&attach.length?(" con "+attach.length+" adjunto"+(attach.length>1?"s":"")):"")):"Abriendo WhatsApp con el mensaje…","ok"); };
  const openEditor = (id)=>{ setSelectedId(id); setView("editor"); setDrawer(false); };
  const newOrder = ()=> flash("Nuevo pedido — abre el armador (fuera de alcance del proto)","ok");

  const sel = orders.find(o=>o.id===selectedId);
  const tweaksForList = {...t, density: t.density==="compacta"?"compact":"regular"};

  const NavItem = ({icon,label,nb,on}) => (
    <a className={"nav-i"+(on?" on":"")} onClick={()=>{setDrawer(false); if(on&&view==="editor")setView("list");}}>
      <Icon name={icon} size={17}/><span>{label}</span>{nb&&<span className="nb">{nb}</span>}
    </a>
  );

  const pendientes = orders.filter(o=>o.tiene_solicitud_pendiente).length;
  const activos = orders.filter(o=>o.estado!=="finalizado"&&o.estado!=="cancelado").length;

  return (
    <div className={"app"+(drawer?" drawer-open":"")}>
      <div className="drawer-scrim" onClick={()=>setDrawer(false)}></div>

      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sb-logo"><img src="assets/rambla-wordmark.svg" alt="Rambla"/><span className="adm">Admin</span></div>
        <nav className="sb-nav">
          <NavItem icon="grid" label="Pedidos" nb={activos} on={true}/>
          <NavItem icon="calendar" label="Calendario"/>
          <div className="sb-sec">Gestión</div>
          <NavItem icon="box" label="Equipo"/>
          <NavItem icon="users" label="Clientes"/>
          <NavItem icon="camera" label="Estudio"/>
          <div className="sb-sec">Sistema</div>
          <NavItem icon="settings" label="Configuración"/>
        </nav>
        <div className="sb-foot">
          <div className="avatar">V</div>
          <div style={{flex:1,minWidth:0}}><div className="nm">Valentina</div><div className="rl">Admin</div></div>
          <button className="iconbtn sm ghost"><Icon name="logout" size={14}/></button>
        </div>
      </aside>

      {/* Main */}
      <div className="main">
        {/* Topbar */}
        <div className="topbar">
          <button className="iconbtn hamb" onClick={()=>setDrawer(true)}><Icon name="menu" size={18}/></button>
          {view==="editor" && sel ? (
            <>
              <button className="back" onClick={()=>setView("list")}><Icon name="chevronL" size={16}/></button>
              <div>
                <div className="crumb">pedidos / {sel.numero_pedido?("#"+String(sel.numero_pedido).padStart(4,"0")):"nuevo"}</div>
                <div style={{display:"flex",alignItems:"center",gap:9}}><h1>{sel.cliente.nombre}</h1><EstadoBadge estado={sel.estado}/></div>
              </div>
              <div style={{flex:1}}></div>
              <span className="saved hide-mobile"><Icon name="check" size={13}/>Guardado</span>
              {sel.cliente.email&&<Btn variant="outline" size="sm" icon="mail" onClick={()=>email(sel)}>Mail</Btn>}
              {sel.cliente.telefono&&<Btn variant="wa" size="sm" icon="whatsapp" onClick={()=>whatsapp(sel)}>WhatsApp</Btn>}
            </>
          ) : (
            <>
              <div className="hide-mobile"><div className="crumb">admin / pedidos</div></div>
              <div className="grow"></div>
              <button className="iconbtn ghost" style={{position:"relative"}}><Icon name="bell" size={17}/>{pendientes>0&&<span style={{position:"absolute",top:7,right:7,width:7,height:7,borderRadius:9999,background:"var(--amber)",border:"1.5px solid var(--surface-elevated)"}}></span>}</button>
              <div className="avatar" style={{width:32,height:32}}>V</div>
            </>
          )}
        </div>

        {/* Content */}
        {view==="list"
          ? <ListView orders={orders} selectedId={selectedId} onSelect={setSelectedId} onOpen={openEditor}
              tweaks={tweaksForList} detailCollapsed={detailCollapsed} setDetailCollapsed={setDetailCollapsed}
              onSetEstado={setEstado} onPago={(id)=>setModal({type:"pago",id})} onWhatsApp={whatsapp} onEmail={email} onNew={newOrder}/>
          : <EditorView o={sel} onSetEstado={setEstado} onPatch={patch} onAddItem={addItem} onRemoveItem={removeItem}
              onQty={setQty} onPago={(id)=>setModal({type:"pago",id})} onWhatsApp={whatsapp} onEmail={email} onResolveSolicitud={resolveSolicitud}/>
        }
      </div>

      {modal&&modal.type==="pago"&&<PagoModal o={orders.find(o=>o.id===modal.id)} onClose={()=>setModal(null)} onSave={savePago}/>}
      {comms&&<CommsModal channel={comms.channel} order={orders.find(o=>o.id===comms.id)} onClose={()=>setComms(null)} onSend={sendComms}/>}

      {toast && <div style={{position:"fixed",bottom:24,left:"50%",transform:"translateX(-50%)",zIndex:200,background:"var(--ink)",color:"var(--background)",padding:"11px 18px",borderRadius:9999,boxShadow:"var(--shadow-lg)",fontSize:13.5,fontWeight:600,display:"flex",alignItems:"center",gap:9,maxWidth:"90vw"}}>
        <Icon name={toast.kind==="err"?"alert":"check"} size={15} style={{color:toast.kind==="err"?"var(--amber)":"var(--amber)"}}/>{toast.msg}
      </div>}

      {/* Tweaks */}
      <TweaksPanel title="Tweaks">
        <TweakSection label="Lista" />
        <TweakRadio label="Densidad" value={t.density} options={["cómoda","compacta"]} onChange={v=>setTweak("density",v)}/>
        <TweakToggle label="Panel de detalle (split)" value={t.preview} onChange={v=>setTweak("preview",v)}/>
        <TweakToggle label="Mostrar cobranza en filas" value={t.showCobranza} onChange={v=>setTweak("showCobranza",v)}/>
        <TweakSection label="Tema" />
        <TweakToggle label="Modo oscuro" value={t.dark} onChange={v=>setTweak("dark",v)}/>
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App/>);
