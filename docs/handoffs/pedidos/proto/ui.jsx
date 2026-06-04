/* UI primitives + estado helpers */
const { Icon } = window;

const ESTADOS = {
  borrador:   {label:"Borrador"},
  presupuesto:{label:"Presupuesto"},
  confirmado: {label:"Confirmado"},
  retirado:   {label:"Retirado"},
  devuelto:   {label:"Devuelto"},
  finalizado: {label:"Finalizado"},
  cancelado:  {label:"Cancelado"},
};
const FLOW = ["presupuesto","confirmado","retirado","devuelto","finalizado"];

// Transiciones válidas (espeja backend ESTADOS_VALIDOS + reglas)
function transitions(o){
  const e = o.estado;
  const map = {
    borrador:   ["presupuesto","cancelado"],
    presupuesto:["confirmado","cancelado"],
    confirmado: ["retirado","cancelado"],
    retirado:   ["devuelto","cancelado"],
    devuelto:   ["finalizado"],
    finalizado: [],
    cancelado:  [],
  };
  return map[e]||[];
}
// motivo por el que un estado destino está bloqueado (validación de fechas/stock/items)
function blockReason(o, target){
  const needsDates = ["confirmado","retirado","devuelto","finalizado"];
  if(needsDates.includes(target)){
    if(!o.fecha_desde || !o.fecha_hasta) return "faltan fechas";
    if(!o.items || !o.items.length) return "sin equipos";
  }
  return null;
}
// La acción "siguiente paso" sugerida
function nextStep(o){
  const t = transitions(o).filter(x=>x!=="cancelado");
  if(!t.length) return null;
  const target = t[0];
  const verbs = {presupuesto:"Confirmar pedido", confirmado:"Marcar retirado", retirado:"Registrar devolución", devuelto:"Cobrar saldo y finalizar", finalizado:""};
  const icons = {confirmado:"check", retirado:"truck", devuelto:"rotate", finalizado:"check"};
  return {target, label:verbs[o.estado]||"Avanzar", icon:icons[target]||"arrowR", blocked:blockReason(o,target)};
}

function EstadoBadge({estado}){
  const m = ESTADOS[estado]||{label:estado};
  return <span className={"badge est-"+estado}><span className="d"></span>{m.label}</span>;
}
function StateDot({estado}){ return <span className={"sdot est-"+estado} style={{background:dotColor(estado)}}></span>; }
function dotColor(e){
  return {borrador:"var(--muted-foreground)",presupuesto:"var(--azul)",confirmado:"var(--verde)",retirado:"var(--amber)",devuelto:"var(--rosa)",finalizado:"color-mix(in oklch,var(--verde) 60%,var(--muted-foreground))",cancelado:"var(--destructive)"}[e]||"var(--muted-foreground)";
}

function Btn({variant="ink", size, pill, block, icon, iconR, children, disabled, onClick, style, title}){
  const cls = ["btn","btn-"+variant];
  if(size) cls.push(size); if(pill) cls.push("pill"); if(block) cls.push("block"); if(disabled) cls.push("is-disabled");
  return (
    <button className={cls.join(" ")} onClick={disabled?undefined:onClick} style={style} title={title}>
      {icon && <Icon name={icon} size={size==="sm"?14:16} sw={2.2}/>}
      {children}
      {iconR && <Icon name={iconR} size={size==="sm"?13:15} sw={2.2}/>}
    </button>
  );
}

function Stepper({value, min=0, max=99, onChange, size}){
  return (
    <div className={"stepper"+(size?" "+size:"")}>
      <button disabled={value<=min} onClick={()=>onChange(Math.max(min,value-1))}><Icon name="minus" size={size==="sm"?11:13} sw={2.5}/></button>
      <span className="q">{value}</span>
      <button disabled={value>=max} onClick={()=>onChange(Math.min(max,value+1))}><Icon name="plus" size={size==="sm"?11:13} sw={2.5}/></button>
    </div>
  );
}

function Field({label, children, style}){
  return <label className="field" style={style}><span className="fl">{label}</span>{children}</label>;
}

Object.assign(window, { ESTADOS, FLOW, transitions, blockReason, nextStep, EstadoBadge, StateDot, dotColor, Btn, Stepper, Field });
