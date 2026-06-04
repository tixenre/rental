/* CommsModal — template picker for WhatsApp & Email */
const { Icon, Btn, Field, RAMBLA } = window;
const { fmtARS, fechaCorta, fechaHora, breakdown, pagado } = RAMBLA;

const TEMPLATE_KEYS = ["presupuesto","confirmado","retiro","devolucion","pago","libre"];
const DOC_LIST = ["Remito","Contrato","Packing","Presupuesto"];
const DEFAULT_ATTACH = {
  presupuesto:["Presupuesto"],
  confirmado:["Contrato","Presupuesto"],
  retiro:["Remito","Packing"],
  devolucion:["Remito"],
  pago:["Presupuesto"],
  libre:[],
};
const TEMPLATE_TITLES = {
  presupuesto:"Presupuesto / cotización",
  confirmado:"Confirmación + seña",
  retiro:"Recordatorio de retiro",
  devolucion:"Recordatorio de devolución",
  pago:"Pago / recibo",
  libre:"Mensaje libre",
};

function suggestedKey(o){
  if(o.estado==="borrador"||o.estado==="presupuesto") return "presupuesto";
  if(o.estado==="confirmado") return o.retiraHoy?"retiro":"confirmado";
  if(o.estado==="retirado") return "devolucion";
  if(o.estado==="devuelto") return "pago";
  return "libre";
}

function ctx(o){
  const b = breakdown(o);
  return {
    first: (o.cliente.nombre||"").replace(/^.*?,\s*/,"").split(" ")[0],
    num: o.numero_pedido?("#"+String(o.numero_pedido).padStart(4,"0")):("#"+o.id),
    items: o.items.map(it=>"• "+it.cantidad+"× "+it.nombre).join("\n"),
    rango: o.fecha_desde?(fechaCorta(o.fecha_desde)+" → "+fechaCorta(o.fecha_hasta)):"a definir",
    desde: o.fecha_desde?fechaHora(o.fecha_desde):"a coordinar",
    hasta: o.fecha_hasta?fechaHora(o.fecha_hasta):"a coordinar",
    J: b.J, total: fmtARS(b.total), senia: fmtARS(Math.round(b.total*0.5)),
    saldo: fmtARS(Math.max(0,b.total-pagado(o))),
  };
}

function buildWA(o,key){
  const c = ctx(o);
  switch(key){
    case "presupuesto": return `Hola ${c.first}, ¿cómo va? Te paso el presupuesto del pedido ${c.num}:\n${c.items}\nFechas: ${c.rango} (${c.J} ${c.J===1?"jornada":"jornadas"}).\nTotal: ${c.total}.\nCualquier duda me escribís. ¡Gracias!`;
    case "confirmado": return `Hola ${c.first}, te confirmo el pedido ${c.num} para el ${c.rango}. Para reservar las fechas necesitamos la seña de ${c.senia}. Te paso los datos cuando quieras. ¡Gracias!`;
    case "retiro": return `Hola ${c.first}, te esperamos para el retiro del pedido ${c.num} el ${c.desde}. Estamos en Rambla, Mar del Plata. ¡Nos vemos!`;
    case "devolucion": return `Hola ${c.first}, te recuerdo que la devolución del pedido ${c.num} es el ${c.hasta}. Cualquier cosa avisanos. ¡Gracias!`;
    case "pago": return `Hola ${c.first}, registramos tu pago del pedido ${c.num}. Saldo pendiente: ${c.saldo}. ¡Gracias!`;
    default: return "";
  }
}
function buildMail(o,key){
  const c = ctx(o);
  const firma = "\n\nSaludos,\nEquipo Rambla Rental";
  switch(key){
    case "presupuesto": return {subject:`Presupuesto pedido ${c.num} — Rambla Rental`, body:`Hola ${c.first},\n\nTe enviamos el presupuesto del pedido ${c.num}:\n\n${c.items}\n\nFechas: ${c.rango} (${c.J} ${c.J===1?"jornada":"jornadas"}).\nTotal: ${c.total}.\n\nQuedamos a disposición para cualquier consulta.${firma}`};
    case "confirmado": return {subject:`Pedido ${c.num} confirmado`, body:`Hola ${c.first},\n\nTu pedido ${c.num} quedó confirmado para el ${c.rango}.\nPara dejar las fechas reservadas necesitamos la seña de ${c.senia}.${firma}`};
    case "retiro": return {subject:`Recordatorio de retiro — pedido ${c.num}`, body:`Hola ${c.first},\n\nTe recordamos que el retiro del pedido ${c.num} es el ${c.desde}, en Rambla (Mar del Plata).${firma}`};
    case "devolucion": return {subject:`Recordatorio de devolución — pedido ${c.num}`, body:`Hola ${c.first},\n\nTe recordamos que la devolución del pedido ${c.num} es el ${c.hasta}.${firma}`};
    case "pago": return {subject:`Recibo de pago — pedido ${c.num}`, body:`Hola ${c.first},\n\nRegistramos tu pago del pedido ${c.num}. Saldo pendiente: ${c.saldo}.${firma}`};
    default: return {subject:"", body:""};
  }
}

function CommsModal({channel, order, onClose, onSend}){
  const isMail = channel==="mail";
  const [key,setKey] = React.useState(()=>suggestedKey(order));
  const init = isMail?buildMail(order,key):{subject:"",body:buildWA(order,key)};
  const [subject,setSubject] = React.useState(init.subject);
  const [body,setBody] = React.useState(init.body);
  const [attach,setAttach] = React.useState(()=>isMail?(DEFAULT_ATTACH[suggestedKey(order)]||[]).slice():[]);
  const sug = suggestedKey(order);

  const toggleAttach = (d)=> setAttach(a=> a.includes(d)? a.filter(x=>x!==d) : [...a,d]);

  const pick = (k)=>{
    setKey(k);
    if(isMail){ const m=buildMail(order,k); setSubject(m.subject); setBody(m.body); setAttach((DEFAULT_ATTACH[k]||[]).slice()); }
    else setBody(buildWA(order,k));
  };

  const dest = isMail ? (order.cliente.email||"sin email") : (order.cliente.telefono||"sin teléfono");

  return (
    <div className="scrim" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}>
      <div className="modal" style={{maxWidth:560}}>
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
          <h3 style={{display:"flex",alignItems:"center",gap:9}}>
            <span style={{color:isMail?"var(--ink)":"var(--verde)"}}><Icon name={isMail?"mail":"whatsapp"} size={19}/></span>
            {isMail?"Enviar por email":"Enviar por WhatsApp"}
          </h3>
          <button className="iconbtn sm ghost" onClick={onClose}><Icon name="x" size={16}/></button>
        </div>
        <div style={{display:"flex",alignItems:"center",gap:8,fontSize:12,color:"var(--muted-foreground)",marginTop:-4}}>
          <span className="mono">{order.cliente.nombre}</span><span>·</span><span className="mono">{dest}</span>
        </div>

        <div>
          <div className="rail-lbl" style={{marginBottom:7}}>Plantilla</div>
          <div className="segrow">
            {TEMPLATE_KEYS.map(k=>(
              <button key={k} className={"chip"+(key===k?" on":"")} onClick={()=>pick(k)}>
                {TEMPLATE_TITLES[k]}{k===sug&&<span className="cnt" style={{fontFamily:"var(--font-mono)",fontSize:8,letterSpacing:".06em"}}>sugerida</span>}
              </button>
            ))}
          </div>
        </div>

        {isMail && (
          <Field label="Asunto"><div className="inp"><input value={subject} onChange={e=>setSubject(e.target.value)} placeholder="Asunto del email"/></div></Field>
        )}
        {isMail && (
          <div>
            <div className="rail-lbl" style={{marginBottom:7,display:"flex",alignItems:"center",gap:6}}><Icon name="link" size={11}/>Adjuntar PDF</div>
            <div className="segrow">
              {DOC_LIST.map(d=>{
                const on = attach.includes(d);
                return <button key={d} className={"docchip"+(on?" on":"")} onClick={()=>toggleAttach(d)}><Icon name={on?"check":"file"} size={12}/>{d}</button>;
              })}
            </div>
          </div>
        )}
        <Field label="Mensaje">
          <textarea className="inp" style={{minHeight:isMail?150:120,fontFamily:isMail?"var(--font-sans)":"var(--font-sans)",lineHeight:1.5}} value={body} onChange={e=>setBody(e.target.value)} placeholder={key==="libre"?"Escribí tu mensaje…":""}/>
        </Field>

        <div style={{display:"flex",gap:8,alignItems:"center"}}>
          <span className="muted" style={{fontSize:11,fontFamily:"var(--font-mono)"}}>{body.length} caracteres{isMail&&attach.length?(" · "+attach.length+" adjunto"+(attach.length>1?"s":"")):""}</span>
          <div style={{flex:1}}></div>
          <Btn variant="ghost" onClick={onClose}>Cancelar</Btn>
          <Btn variant={isMail?"ink":"wa"} pill icon={isMail?"send":"whatsapp"} onClick={()=>onSend(channel,key,isMail?attach:null)}>{isMail?"Enviar email":"Abrir WhatsApp"}</Btn>
        </div>
      </div>
    </div>
  );
}
window.CommsModal = CommsModal;
