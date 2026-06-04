/* Rambla — mock data + helpers (mirrors backend alquileres model) */
(function(){
  // "Hoy" del prototipo = lun 1 jun 2026
  const TODAY = new Date(2026,5,1);
  const MES = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];
  const DIA = ["dom","lun","mar","mié","jue","vie","sáb"];

  function d(y,m,day,h,min){ return new Date(y,m-1,day,h||0,min||0); }
  function fmtARS(n){ if(n==null) return "consultar"; const x=Math.round(Number(n)||0); return "$ "+x.toLocaleString("es-AR").replace(/,/g,"."); }
  function fechaCorta(dt){ if(!dt) return "—"; return DIA[dt.getDay()]+" "+dt.getDate()+" "+MES[dt.getMonth()]; }
  function fechaHora(dt){ if(!dt) return "—"; let s=DIA[dt.getDay()]+" "+dt.getDate()+" "+MES[dt.getMonth()]; if(dt.getHours()||dt.getMinutes()) s+=" · "+String(dt.getHours()).padStart(2,"0")+":"+String(dt.getMinutes()).padStart(2,"0"); return s; }
  function jornadas(a,b){ if(!a||!b) return 1; return Math.max(1, Math.ceil((b-a)/(1000*60*60*24))); }
  function sameDay(a,b){ return a&&b&&a.getFullYear()===b.getFullYear()&&a.getMonth()===b.getMonth()&&a.getDate()===b.getDate(); }
  function initials(name){ const p=name.replace(/^.*?,\s*/,'').split(/\s+/); return ((p[0]||'')[0]||'')+((p[1]||'')[0]||''); }

  // Catálogo para "agregar equipo"
  const CATALOGO = [
    {id:1, nombre:"Sony FX3", marca:"Sony", precio_jornada:18000, stock:3, cat:"cámara"},
    {id:2, nombre:"Sony A7S III", marca:"Sony", precio_jornada:14500, stock:2, cat:"cámara"},
    {id:3, nombre:"Aputure 600d Pro", marca:"Aputure", precio_jornada:9500, stock:4, cat:"luz"},
    {id:4, nombre:"Aputure 300x", marca:"Aputure", precio_jornada:7000, stock:5, cat:"luz"},
    {id:5, nombre:"DJI RS4 Pro", marca:"DJI", precio_jornada:6500, stock:3, cat:"gimbal"},
    {id:6, nombre:"Sennheiser MKH 416", marca:"Sennheiser", precio_jornada:5500, stock:2, cat:"audio"},
    {id:7, nombre:"Kit Grip Completo", marca:"Rambla", precio_jornada:6000, stock:2, cat:"grip", kit:true, componentes:["Trípode", "Dolly", "C-stands ×3", "Banderas"]},
    {id:8, nombre:"Blackmagic ATEM Mini", marca:"Blackmagic", precio_jornada:8000, stock:1, cat:"switcher"},
    {id:9, nombre:"Godox AD600", marca:"Godox", precio_jornada:5000, stock:3, cat:"luz"},
    {id:10, nombre:"Zoom H6", marca:"Zoom", precio_jornada:3000, stock:4, cat:"audio"},
    {id:11, nombre:"Sigma 18-35 f1.8", marca:"Sigma", precio_jornada:4500, stock:3, cat:"lente"},
    {id:12, nombre:"Monitor SmallHD 702", marca:"SmallHD", precio_jornada:5000, stock:2, cat:"monitor"},
  ];

  const orders = [
    {
      id:41, numero_pedido:41, estado:"presupuesto", fuente:null, createdAgo:"hace 2 h", isNew:true,
      cliente:{nombre:"Lucía Fernández", email:"lucia@productora.com", telefono:"+54 223 555-0142", perfil:"consumidor_final", tipo:"estudio · productora"},
      fecha_desde:d(2026,6,2,10,0), fecha_hasta:d(2026,6,5,18,0),
      descuento_pct:10,
      items:[
        {equipo_id:1, nombre:"Sony FX3", marca:"Sony", precio_jornada:18000, cantidad:2},
        {equipo_id:3, nombre:"Aputure 600d Pro", marca:"Aputure", precio_jornada:9500, cantidad:1},
        {equipo_id:7, nombre:"Kit Grip Completo", marca:"Rambla", precio_jornada:6000, cantidad:2, kit:true, componentes:["Trípode","Dolly","C-stands ×3","Banderas"]},
      ],
      pagos:[], notas:"Retira el asistente. Pidió presupuesto formal para aprobar con la productora.",
    },
    {
      id:40, numero_pedido:40, estado:"confirmado", fuente:null, createdAgo:"hace 1 día",
      cliente:{nombre:"Martín Quiroga", email:"martin.q@gmail.com", telefono:"+54 223 544-9810", perfil:"consumidor_final", tipo:"freelance"},
      fecha_desde:d(2026,6,1,10,0), fecha_hasta:d(2026,6,6,18,0),
      descuento_pct:0,
      items:[
        {equipo_id:2, nombre:"Sony A7S III", marca:"Sony", precio_jornada:14500, cantidad:1},
        {equipo_id:5, nombre:"DJI RS4 Pro", marca:"DJI", precio_jornada:6500, cantidad:1},
      ],
      pagos:[{monto:30000, concepto:"Seña", fecha:"2026-05-28"}], notas:"",
    },
    {
      id:39, numero_pedido:39, estado:"retirado", fuente:null, createdAgo:"hace 4 días",
      cliente:{nombre:"Estudio Norte SA", email:"prod@estudionorte.com", telefono:"+54 223 510-2233", perfil:"responsable_inscripto", tipo:"resp. inscripto · IVA"},
      fecha_desde:d(2026,5,31,9,0), fecha_hasta:d(2026,6,1,19,0),
      descuento_pct:5,
      items:[
        {equipo_id:1, nombre:"Sony FX3", marca:"Sony", precio_jornada:18000, cantidad:2},
        {equipo_id:3, nombre:"Aputure 600d Pro", marca:"Aputure", precio_jornada:9500, cantidad:3},
        {equipo_id:8, nombre:"Blackmagic ATEM Mini", marca:"Blackmagic", precio_jornada:8000, cantidad:1},
        {equipo_id:12, nombre:"Monitor SmallHD 702", marca:"SmallHD", precio_jornada:5000, cantidad:2},
      ],
      pagos:[{monto:120000, concepto:"Seña 50%", fecha:"2026-05-29"}], notas:"Factura A. Coordina logística con Pablo.",
    },
    {
      id:38, numero_pedido:38, estado:"confirmado", fuente:null, createdAgo:"hace 3 días",
      cliente:{nombre:"Caro Méndez", email:"caro.mendez@gmail.com", telefono:"+54 223 533-7788", perfil:"consumidor_final", tipo:"fotógrafa"},
      fecha_desde:d(2026,6,4,11,0), fecha_hasta:d(2026,6,8,18,0),
      descuento_pct:0,
      items:[
        {equipo_id:9, nombre:"Godox AD600", marca:"Godox", precio_jornada:5000, cantidad:2},
        {equipo_id:11, nombre:"Sigma 18-35 f1.8", marca:"Sigma", precio_jornada:4500, cantidad:1},
      ],
      pagos:[{monto:42000, concepto:"Pago total", fecha:"2026-05-30"}], notas:"",
      solicitud:{tipo:"fechas", mensaje:"¿Puedo mover el retiro al miércoles 4 y devolver el domingo 8?", was:"mié 4 → sáb 6 jun", now:"mié 4 → dom 8 jun"},
    },
    {
      id:37, numero_pedido:37, estado:"devuelto", fuente:null, createdAgo:"hace 6 días",
      cliente:{nombre:"Sol Aguirre", email:"sol.aguirre@gmail.com", telefono:"+54 223 522-0091", perfil:"consumidor_final", tipo:"realizadora"},
      fecha_desde:d(2026,5,28,10,0), fecha_hasta:d(2026,6,1,12,0),
      descuento_pct:0,
      items:[
        {equipo_id:4, nombre:"Aputure 300x", marca:"Aputure", precio_jornada:7000, cantidad:2},
        {equipo_id:10, nombre:"Zoom H6", marca:"Zoom", precio_jornada:3000, cantidad:1},
      ],
      pagos:[{monto:30000, concepto:"Seña", fecha:"2026-05-26"}], notas:"Devolvió todo OK. Falta saldo.",
    },
    {
      id:36, numero_pedido:36, estado:"presupuesto", fuente:null, createdAgo:"hace 5 h", isNew:true,
      cliente:{nombre:"Pedro Salas", email:"pedro@salasfilms.com", telefono:"+54 223 588-1020", perfil:"consumidor_final", tipo:"productor"},
      fecha_desde:d(2026,6,10,10,0), fecha_hasta:d(2026,6,12,18,0),
      descuento_pct:0,
      items:[
        {equipo_id:6, nombre:"Sennheiser MKH 416", marca:"Sennheiser", precio_jornada:5500, cantidad:1},
        {equipo_id:10, nombre:"Zoom H6", marca:"Zoom", precio_jornada:3000, cantidad:1},
      ],
      pagos:[], notas:"",
    },
    {
      id:35, numero_pedido:null, estado:"borrador", fuente:null, createdAgo:"hace 20 min", isNew:true,
      cliente:{nombre:"Nadia Ríos", email:"", telefono:"+54 223 577-3344", perfil:"consumidor_final", tipo:""},
      fecha_desde:null, fecha_hasta:null, descuento_pct:0,
      items:[{equipo_id:5, nombre:"DJI RS4 Pro", marca:"DJI", precio_jornada:6500, cantidad:1}],
      pagos:[], notas:"Llamó por teléfono, falta confirmar fechas.",
    },
    {
      id:33, numero_pedido:33, estado:"retirado", fuente:null, createdAgo:"hace 5 días",
      cliente:{nombre:"Joaco Pérez", email:"joaco.perez@gmail.com", telefono:"+54 223 566-7711", perfil:"consumidor_final", tipo:"freelance"},
      fecha_desde:d(2026,5,29,10,0), fecha_hasta:d(2026,6,7,18,0),
      descuento_pct:0,
      items:[{equipo_id:1, nombre:"Sony FX3", marca:"Sony", precio_jornada:18000, cantidad:1}],
      pagos:[{monto:54000, concepto:"Seña", fecha:"2026-05-27"}], notas:"",
    },
    {
      id:30, numero_pedido:30, estado:"finalizado", fuente:"booqable-historico", createdAgo:"abr 2026",
      cliente:{nombre:"Registro manual", email:"", telefono:"", perfil:"consumidor_final", tipo:"histórico importado"},
      fecha_desde:d(2026,4,10,10,0), fecha_hasta:d(2026,4,14,18,0), descuento_pct:0,
      items:[{equipo_id:3, nombre:"Aputure 600d Pro", marca:"Aputure", precio_jornada:9500, cantidad:2}],
      pagos:[{monto:71000, concepto:"Total", fecha:"2026-04-10"}], notas:"",
    },
    {
      id:29, numero_pedido:29, estado:"cancelado", fuente:null, createdAgo:"hace 8 días",
      cliente:{nombre:"Belén Costa", email:"belu.costa@gmail.com", telefono:"+54 223 511-9090", perfil:"consumidor_final", tipo:""},
      fecha_desde:d(2026,5,30,10,0), fecha_hasta:d(2026,6,2,18,0), descuento_pct:0,
      items:[{equipo_id:2, nombre:"Sony A7S III", marca:"Sony", precio_jornada:14500, cantidad:1}],
      pagos:[], notas:"Canceló por reprogramación de rodaje.",
    },
  ];

  // ── derived flags + breakdown ──
  function pagado(o){ return (o.pagos||[]).reduce((s,p)=>s+p.monto,0); }
  function breakdown(o){
    const J = jornadas(o.fecha_desde, o.fecha_hasta);
    const bruto = o.items.reduce((s,it)=>s+it.precio_jornada*it.cantidad,0)*J;
    const desc = Math.round(bruto*(o.descuento_pct||0)/100);
    const neto = bruto-desc;
    const conIva = o.cliente.perfil==="responsable_inscripto";
    const iva = conIva ? Math.round(neto*0.21) : 0;
    const total = neto+iva;
    return {J,bruto,desc,neto,conIva,iva,total};
  }
  function montoTotal(o){ return breakdown(o).neto; } // neto persistido
  orders.forEach(o=>{
    o.retiraHoy = o.estado==="confirmado" && sameDay(o.fecha_desde, TODAY);
    o.devuelveHoy = o.estado==="retirado" && sameDay(o.fecha_hasta, TODAY);
    o.tiene_solicitud_pendiente = !!o.solicitud;
  });

  window.RAMBLA = { TODAY, orders, CATALOGO, fmtARS, fechaCorta, fechaHora, jornadas, sameDay, initials, pagado, breakdown, montoTotal, MES, DIA };
})();
