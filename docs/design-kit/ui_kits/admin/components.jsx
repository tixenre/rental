/* Admin back-office components */
const { useState, useMemo } = React;

// ── Sidebar ───────────────────────────────────────────────────────────
function Sidebar({ section, setSection }) {
  const [openInv, setOpenInv] = useState(true);
  const Item = ({ id, icon: I, label, open, hasChildren, sub }) => (
    <button
      className={"nav-item" + (section === id ? " active" : "") + (open ? " open" : "")}
      onClick={() => {
        if (hasChildren) setOpenInv(!openInv);
        setSection(id);
      }}
    >
      <I /> <span>{label}</span>
      {hasChildren && <AChevronRight className="chevron" />}
    </button>
  );
  const SubItem = ({ id, icon: I, label }) => (
    <button className={"nav-item" + (section === id ? " active" : "")} onClick={() => setSection(id)}>
      <I /> <span>{label}</span>
    </button>
  );

  return (
    <aside className="sidebar">
      <div className="sidebar-head">
        <div className="brand-mark">
          <img src="../../assets/rambla-icon-r.png" alt="Rambla" />
        </div>
        <div>
          <div className="brand-name">Rambla Rental</div>
          <div className="brand-sub">Back-office</div>
        </div>
      </div>
      <nav>
        <div className="nav-group-label">General</div>
        <Item id="dashboard" icon={ALayoutDashboard} label="Dashboard" />
        <Item id="inventario" icon={APackage} label="Inventario" hasChildren open={openInv} />
        {openInv && (
          <div className="nav-sub">
            <SubItem id="equipos" icon={AList} label="Equipos" />
            <SubItem id="categorias" icon={AFolderTree} label="Categorías" />
            <SubItem id="marcas" icon={ABuilding} label="Marcas" />
            <SubItem id="etiquetas" icon={ATag} label="Etiquetas" />
            <SubItem id="specs" icon={AWrench} label="Specs por categoría" />
          </div>
        )}
        <Item id="pedidos" icon={AClipboard} label="Pedidos" />
        <Item id="clientes" icon={AUsers} label="Clientes" />
        <Item id="estadisticas" icon={AChart} label="Estadísticas" />
        <Item id="diseno" icon={APalette} label="Diseño" />
        <Item id="novedades" icon={ASparkles} label="Novedades" />
        <Item id="settings" icon={ASettings} label="Settings" />
      </nav>
      <div className="sidebar-foot">
        <div className="user-row">
          <div className="avatar">MS</div>
          <div className="user-info">
            <div className="user-name">Martin Santini</div>
            <div className="user-email">ramblarental@gmail.com</div>
          </div>
        </div>
        <button className="logout"><ALogOut /> <span>Cerrar sesión</span></button>
      </div>
    </aside>
  );
}

// ── KPIs (dashboard strip used at the top of equipos list) ───────────
function KPIStrip() {
  return (
    <div className="kpis">
      <div className="kpi">
        <div className="label">Equipos en catálogo</div>
        <div className="val">187</div>
        <div className="delta up">↑ 4 esta semana</div>
      </div>
      <div className="kpi">
        <div className="label">Pedidos activos</div>
        <div className="val">12</div>
        <div className="delta up">↑ 2 vs ayer</div>
      </div>
      <div className="kpi">
        <div className="label">Por cobrar (ARS)</div>
        <div className="val">$ 482.500</div>
        <div className="delta down">3 vencidos</div>
      </div>
      <div className="kpi">
        <div className="label">Mantenimiento</div>
        <div className="val">2</div>
        <div className="delta down">vencidos</div>
      </div>
    </div>
  );
}

// ── Toolbar ──────────────────────────────────────────────────────────
function Toolbar({ query, setQuery, catFilter, setCatFilter, brandFilter, setBrandFilter, stateFilter, setStateFilter }) {
  const cats = ["Todas", "Cámaras", "Lentes", "Iluminación", "Audio", "Soportes"];
  const brands = ["Todas", "Sony", "Canon", "Fujifilm", "DJI", "Aputure", "Sennheiser", "Rode", "Sachtler"];
  const states = ["Todos", "Visible", "Oculto", "Ficha incompleta", "En mantenimiento"];
  return (
    <div className="toolbar">
      <div className="search-wrap">
        <ASearch size={14} />
        <input
          placeholder="Buscar por nombre, marca, modelo, serie…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      <Pick label={catFilter === "Todas" ? "Categoría" : catFilter} options={cats} value={catFilter} onChange={setCatFilter} />
      <Pick label={brandFilter === "Todas" ? "Marca" : brandFilter} options={brands} value={brandFilter} onChange={setBrandFilter} />
      <Pick label={stateFilter === "Todos" ? "Estado" : stateFilter} options={states} value={stateFilter} onChange={setStateFilter} />
      <div style={{flex: 1}} />
      <button className="btn btn-outline"><AFilter /> Más filtros</button>
    </div>
  );
}
function Pick({ label, options, value, onChange }) {
  const [open, setOpen] = useState(false);
  const isFiltered = value && !value.startsWith("Tod");
  return (
    <div style={{position: "relative"}}>
      <button
        className={"dropdown" + (isFiltered ? " active" : "")}
        onClick={() => setOpen(!open)}
      >
        {label}
        <AChevronRight style={{transform: open ? "rotate(90deg)" : "rotate(0deg)", transition: "transform .15s"}} />
      </button>
      {open && (
        <div style={{
          position: "absolute", top: "100%", left: 0, marginTop: 4, zIndex: 5,
          background: "var(--surface-elevated)", border: "1px solid var(--hairline)",
          borderRadius: 8, padding: 4, minWidth: 160, boxShadow: "0 8px 24px -8px rgba(20,16,12,.18)",
        }}>
          {options.map((o) => (
            <button
              key={o}
              onClick={() => { onChange(o); setOpen(false); }}
              style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "6px 10px", borderRadius: 5, border: 0, background: o === value ? "var(--amber-soft)" : "transparent",
                cursor: "pointer", width: "100%", fontFamily: "var(--font-sans)", fontSize: 12.5,
                color: "var(--ink)", textAlign: "left",
              }}
            >
              {o}
              {o === value && <ACheck size={12} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Equipment table ──────────────────────────────────────────────────
function EquiposTable({ items, selected, toggle, toggleAll }) {
  const allChecked = items.length > 0 && items.every(i => selected.has(i.id));
  const someChecked = !allChecked && items.some(i => selected.has(i.id));
  return (
    <table className="eq-table">
      <thead>
        <tr>
          <th style={{width: 32}}>
            <Checkbox checked={allChecked} indeterminate={someChecked} onChange={() => toggleAll(!allChecked)} />
          </th>
          <th style={{width: 54}}></th>
          <th>Equipo</th>
          <th>Categoría</th>
          <th>Estado</th>
          <th style={{textAlign: "right"}}>Stock</th>
          <th style={{textAlign: "right"}}>$ / jornada</th>
          <th style={{textAlign: "right"}}>% día</th>
          <th>Etiquetas</th>
          <th style={{width: 90}}></th>
        </tr>
      </thead>
      <tbody>
        {items.map((e) => {
          const initials = e.name.split(/\s+/).slice(0,2).map(p => p[0]).join("").toUpperCase();
          const isSel = selected.has(e.id);
          return (
            <tr key={e.id} className={isSel ? "selected" : ""}>
              <td><Checkbox checked={isSel} onChange={() => toggle(e.id)} /></td>
              <td><div className="thumb">{initials}</div></td>
              <td>
                <div className="name">
                  <span className="nm">{e.name}{e.new && <span style={{marginLeft: 6, fontFamily: "var(--font-mono)", fontSize: 9, letterSpacing: "0.18em", textTransform: "uppercase", background: "var(--ink)", color: "var(--amber)", padding: "2px 6px", borderRadius: 9999}}>nuevo</span>}</span>
                  <span className="br">{e.brand}</span>
                </div>
              </td>
              <td>{e.cat}</td>
              <td><StateBadge state={e.state} /></td>
              <td className="num" style={{textAlign: "right"}}>{e.stock}</td>
              <td className="num" style={{textAlign: "right"}}>$ {e.price.toLocaleString("es-AR")}</td>
              <td style={{textAlign: "right"}}>
                <span className={"roi " + (e.roiPct < 3 ? "bad" : e.roiPct < 5 ? "low" : "")}>{e.roiPct.toFixed(1)}%</span>
              </td>
              <td>
                <div className="tags">
                  {e.tags.slice(0, 2).map((t) => <span className="tag" key={t}>{t}</span>)}
                  {e.tags.length > 2 && <span className="tag">+{e.tags.length - 2}</span>}
                </div>
              </td>
              <td>
                <div className="row-actions">
                  <button title="Editar"><APencil /></button>
                  <button title="Mantenimiento"><AWrench /></button>
                  <button title={e.state === "visible" ? "Ocultar" : "Mostrar"}>
                    {e.state === "visible" ? <AEyeOff /> : <AEye />}
                  </button>
                  <button title="Más"><AMore /></button>
                </div>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function Checkbox({ checked, indeterminate, onChange }) {
  return (
    <span
      className={"cb" + (checked || indeterminate ? " checked" : "")}
      onClick={onChange}
      role="checkbox"
      aria-checked={checked}
    >
      {indeterminate && !checked && (
        <span style={{
          position: "absolute", width: 8, height: 2, background: "var(--ink)",
          borderRadius: 1,
        }} />
      )}
    </span>
  );
}

function StateBadge({ state }) {
  const map = {
    visible:     { cls: "visible",     label: "Visible" },
    hidden:      { cls: "hidden",      label: "Oculto" },
    incomplete:  { cls: "incomplete",  label: "Incompleto" },
    maintenance: { cls: "maintenance", label: "Mantenim." },
  };
  const v = map[state] || map.hidden;
  return <span className={"badge-state " + v.cls}>{v.label}</span>;
}

// ── Bulk action bar ──────────────────────────────────────────────────
function BulkBar({ count, onClear, onShow, onHide, onDelete }) {
  if (count === 0) return null;
  return (
    <div className="bulkbar">
      <span><span className="count">{count}</span> seleccionados</span>
      <span className="divider"></span>
      <button onClick={onShow}><AEye /> Mostrar</button>
      <button onClick={onHide}><AEyeOff /> Ocultar</button>
      <button onClick={onDelete} className="danger"><ATrash /> Eliminar</button>
      <span className="divider"></span>
      <button onClick={onClear}><AX /> Limpiar</button>
    </div>
  );
}

Object.assign(window, { Sidebar, KPIStrip, Toolbar, EquiposTable, BulkBar });
