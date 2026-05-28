/* Public catalog UI Kit — composed components.
 * All in one file for legibility — splitting kept the bundle small.
 */
const { useState, useMemo } = React;

// ── TopBar ────────────────────────────────────────────────────────────
function TopBar({ cartCount, onCartOpen, onDateOpen, hasDates, dateLabel, jornadas }) {
  return (
    <header className="topbar">
      <div className="topbar-inner">
        <a href="#" className="logo-link" aria-label="Rambla Rental">
          <img className="logo-img" src="../../assets/rambla-wordmark.webp" alt="Rambla Rental" />
        </a>
        <button className="date-pill" onClick={onDateOpen} aria-label={hasDates ? "Editar fechas" : "Elegir fechas"}>
          <span className="ical"><IconCalendar size={16} /></span>
          {hasDates ? (
            <>
              <span>{dateLabel}</span>
              <span className="meta-jornadas">· {jornadas} {jornadas === 1 ? "jornada" : "jornadas"}</span>
            </>
          ) : (
            <span>Elegir fechas</span>
          )}
        </button>
        <div className="tb-actions">
          <button className="cart-btn" onClick={onCartOpen} aria-label={`Carrito (${cartCount})`}>
            <IconShoppingBag size={16} />
            <span className="num">{cartCount}</span>
            <span>{cartCount === 1 ? "ítem" : "ítems"}</span>
          </button>
          <a className="ingresar" href="#cliente">
            <IconUser size={16} /><span>Ingresar</span>
          </a>
        </div>
      </div>
    </header>
  );
}

// ── Hero (amber slab with the chunky tagline) ──────────────────────────
function Hero() {
  return (
    <section className="hero grain">
      <div className="pad">
        <div className="eyebrow">Catálogo · {EQUIPMENT.length} equipos · Mar del Plata</div>
        <h1 className="tagline">un lugar<br/>donde pasan<br/>cosas.</h1>
        <p className="sub">
          Cámaras, ópticas, luces, audio y soportes para producciones audiovisuales.
          Elegí fechas y armá tu pedido — te lo dejamos listo para retirar.
        </p>
        <div className="estudio-card">
          <div className="left">
            <span className="pill"><IconSparkles size={12} /> Espacio Rambla</span>
            <div className="title">Conocé el Estudio</div>
            <div className="desc">Foto y video · reservá por hora · pack de luces y grips opcional</div>
          </div>
          <a className="go" href="#estudio">Ver estudio <IconArrowRight size={16} /></a>
        </div>
      </div>
    </section>
  );
}

// ── Sub-toolbar ───────────────────────────────────────────────────────
function SubToolbar({ mode, setMode, query, setQuery, visibleCount, total }) {
  return (
    <div className="subtoolbar">
      <div className="subtoolbar-inner">
        <div className="view-toggle">
          <button className={mode === "grid" ? "active" : ""} onClick={() => setMode("grid")}>
            <IconGrid /> <span>Explorar</span>
          </button>
          <button className={mode === "list" ? "active" : ""} onClick={() => setMode("list")}>
            <IconList /> <span>Lista</span>
          </button>
        </div>
        <div className="search-wrap">
          <IconSearch size={16} className="search-icon" />
          <input
            placeholder="Buscar equipo, marca…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <div className="counter">
          {query.trim() ? `${visibleCount} resultados` : `${total} equipos`}
        </div>
      </div>
    </div>
  );
}

// ── Category mosaic ──────────────────────────────────────────────────
function CategoryMosaic({ categories, selected, onSelect, counts }) {
  return (
    <section className="section">
      <header>
        <div className="left">
          <div className="eyebrow">buscá por</div>
          <h2 className="title-wm">categorías</h2>
        </div>
        <div className="count-r">{categories.length} familias</div>
      </header>
      <div className="cat-grid">
        {categories.map((c) => {
          const Ill = CATEGORY_ILLS[c];
          const count = counts[c] || 0;
          const active = selected === c;
          return (
            <button
              key={c}
              type="button"
              className={"cat-tile" + (active ? " active" : "")}
              onClick={() => onSelect(active ? null : c)}
            >
              <span className="cat-icon">{Ill ? <Ill /> : null}</span>
              <div className="bot">
                <span className="name">{c}</span>
                <span className="count-mono">{count}</span>
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}

// ── Brand row ────────────────────────────────────────────────────────
function BrandLogo({ icon, name, failed, onError }) {
  if (icon && !failed) {
    return (
      <img
        className="logo"
        src={`https://cdn.simpleicons.org/${icon}/000`}
        alt={name}
        onError={onError}
      />
    );
  }
  const initials = name.length <= 4 ? name.toUpperCase() : name.slice(0, 2).toUpperCase();
  return <span className="initials">{initials}</span>;
}

function BrandRow({ brands, selected, onSelect }) {
  const [failed, setFailed] = useState({});
  return (
    <section className="section">
      <header>
        <div className="left">
          <div className="eyebrow">Marcas</div>
          <h2>Marcas destacadas</h2>
        </div>
        <div className="count-r">{brands.length} marcas</div>
      </header>
      <div className="brand-row">
        {brands.map((b) => {
          const active = selected === b.nombre;
          return (
            <button
              key={b.nombre}
              type="button"
              className={"brand-card" + (active ? " active" : "")}
              onClick={() => onSelect(active ? null : b.nombre)}
              title={b.nombre}
              aria-label={`Filtrar por ${b.nombre}`}
            >
              <BrandLogo
                icon={b.icon}
                name={b.nombre}
                failed={failed[b.nombre]}
                onError={() => setFailed((s) => ({ ...s, [b.nombre]: true }))}
              />
            </button>
          );
        })}
      </div>
    </section>
  );
}

// ── Equipment card ───────────────────────────────────────────────────
function EquipmentCard({ item, qty, onAdd, onRemove, onOpen }) {
  const noStock = item.cantidad === 0;
  const stockBajo = item.cantidad > 0 && item.cantidad <= 2;
  const selected = qty > 0;
  const reachedMax = qty >= item.cantidad;
  const cls = "eq" + (selected ? " selected" : "") + (noStock ? " sin-stock" : "");

  const thumbInitials = useMemo(() => {
    const parts = item.name.split(/\s+/);
    return parts.slice(1, 3).map((p) => p[0]).join("").toUpperCase() || "—";
  }, [item.name]);

  const handleOpen = (e) => { if (onOpen) { e.stopPropagation(); onOpen(item.id); } };

  return (
    <article className={cls}>
      <div className="photo" onClick={handleOpen} role="button">
        {item.isNew && !selected && (
          <span className="badge-new"><IconSparkles size={10}/> nuevo</span>
        )}
        {item.destacado && !selected && !item.isNew && (
          <span className="badge-destacado">★ destacado</span>
        )}
        {selected && (
          <span className="badge-check"><IconCheck size={14} strokeWidth={3.5} /></span>
        )}
        <div className="placeholder">
          {thumbInitials}
        </div>
        {noStock && (
          <div className="sin-overlay"><span className="sin-pill">Sin stock</span></div>
        )}
      </div>
      <div className="info">
        <div className="meta" onClick={handleOpen}>
          <div className="name">{item.name}</div>
          <div className="pricerow">
            <div className="price-block">
              <span className="price">{formatARS(item.pricePerDay)}</span>
              <span className="per">/ jornada</span>
            </div>
            {qty === 0 ? (
              <button
                className="add"
                onClick={(e) => { e.stopPropagation(); !noStock && onAdd(item.id); }}
                disabled={noStock}
                aria-label="Agregar al carrito"
              >
                <IconPlus size={16}/>
              </button>
            ) : (
              <div className="qty">
                <button onClick={(e) => { e.stopPropagation(); onRemove(item.id); }} aria-label="Quitar uno">
                  <IconMinus size={14}/>
                </button>
                <span className="num">{qty}</span>
                <button onClick={(e) => { e.stopPropagation(); !reachedMax && onAdd(item.id); }} disabled={reachedMax} aria-label="Sumar uno">
                  <IconPlus size={14}/>
                </button>
              </div>
            )}
          </div>
          <span className={"stock-r " + (noStock ? "out" : stockBajo ? "low" : "normal")}>
            {noStock ? "Sin stock" : `${item.cantidad} disp.`}
          </span>
        </div>
      </div>
    </article>
  );
}

// ── Category carousel ────────────────────────────────────────────────
function CategoryCarousel({ category, items, cart, onAdd, onRemove, onOpen }) {
  if (items.length === 0) return null;
  return (
    <section className="section">
      <header>
        <div className="left">
          <h2>{category}</h2>
        </div>
        <div className="count-r">{items.length} {items.length === 1 ? "equipo" : "equipos"}</div>
      </header>
      <div className="carousel">
        {items.map((item) => (
          <EquipmentCard
            key={item.id}
            item={item}
            qty={cart[item.id] || 0}
            onAdd={onAdd}
            onRemove={onRemove}
            onOpen={onOpen}
          />
        ))}
      </div>
    </section>
  );
}

// ── Footer ───────────────────────────────────────────────────────────
function Footer() {
  return (
    <footer className="footer">
      <div className="footer-inner">
        <div className="footer-grid">
          <div className="brand">
            <img src="../../assets/rambla-wordmark.webp" alt="Rambla Rental" />
            <p>Equipos audiovisuales y estudio de foto/video en Mar del Plata. Producciones de cualquier escala.</p>
            <button className="wa-btn">
              <IconMessage size={16} /> Consultanos por WhatsApp
            </button>
          </div>
          <div className="col">
            <h3>Contacto</h3>
            <ul>
              <li><IconMapPin /><span>Chaco 1392<br/><span style={{color: "var(--muted-foreground)"}}>Mar del Plata, Buenos Aires</span></span></li>
              <li><IconPhone /><span className="mono">+54 9 223 585-2510</span></li>
              <li><IconMail /><a href="#">ramblarental@gmail.com</a></li>
              <li><IconClock /><span style={{color: "var(--muted-foreground)"}}>
                <span style={{color: "var(--ink)"}}>Lun–Vie:</span> 10:00–19:00<br/>
                <span style={{color: "var(--ink)"}}>Sábado:</span> 10:00–14:00
              </span></li>
            </ul>
          </div>
          <div className="col">
            <h3>Navegación</h3>
            <ul>
              <li><a href="#">Catálogo</a></li>
              <li><a href="#">El Estudio</a></li>
              <li><a href="#">Preguntas frecuentes</a></li>
              <li><a href="#"><IconInstagram /><span>@rambla.rental</span></a></li>
            </ul>
          </div>
        </div>
        <div className="legal">
          <div>
            <span>© 2026 Rambla Rental</span>
            <span style={{marginLeft: "16px"}}><a href="#">Privacidad</a></span>
            <span style={{marginLeft: "16px"}}><a href="#">Términos</a></span>
          </div>
          <div className="right">
            <span>Aceptamos:</span>
            <span className="ink">Efectivo</span>
            <span className="ink">Transferencia</span>
            <span className="ink">MercadoPago</span>
          </div>
        </div>
      </div>
    </footer>
  );
}

// ── Cart Drawer ──────────────────────────────────────────────────────
function CartDrawer({ open, onClose, cart, equipment, onAdd, onRemove, jornadas }) {
  const items = Object.keys(cart).filter((id) => cart[id] > 0).map((id) => {
    const eq = equipment.find((e) => e.id === id);
    return eq ? { eq, qty: cart[id] } : null;
  }).filter(Boolean);

  const subtotal = items.reduce((sum, { eq, qty }) => sum + eq.pricePerDay * qty * jornadas, 0);

  return (
    <>
      <div className={"scrim" + (open ? " open" : "")} onClick={onClose}></div>
      <div className={"drawer" + (open ? " open" : "")}>
        <div className="drawer-head">
          <h3>Tu pedido</h3>
          <button className="drawer-close" onClick={onClose} aria-label="Cerrar">
            <IconX size={18}/>
          </button>
        </div>
        <div className="drawer-body">
          {items.length === 0 ? (
            <div className="drawer-empty">
              Tu carrito está vacío.<br/><br/>
              <span style={{fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.22em", textTransform: "uppercase"}}>
                Sumá equipos desde el catálogo
              </span>
            </div>
          ) : items.map(({ eq, qty }) => {
            const initials = eq.name.split(/\s+/).slice(0,2).map(p => p[0]).join("").toUpperCase();
            return (
              <div className="cart-item" key={eq.id}>
                <div className="thumb">{initials}</div>
                <div className="info">
                  <div className="b">{eq.brand}</div>
                  <div className="n">{eq.name}</div>
                  <div className="p">{formatARS(eq.pricePerDay)} /jornada</div>
                </div>
                <div className="qty">
                  <button onClick={() => onRemove(eq.id)}><IconMinus size={14}/></button>
                  <span className="num">{qty}</span>
                  <button onClick={() => onAdd(eq.id)}><IconPlus size={14}/></button>
                </div>
              </div>
            );
          })}
        </div>
        {items.length > 0 && (
          <div className="drawer-foot">
            <div className="totalrow">
              <span className="lbl">Subtotal · {jornadas} {jornadas === 1 ? "jornada" : "jornadas"}</span>
              <span className="val">{formatARS(subtotal)}</span>
            </div>
            <button className="checkout">Continuar a cotización</button>
          </div>
        )}
      </div>
    </>
  );
}

// ── List mode: compact horizontal row with inline expansion ──────────
function EquipmentRow({ item, qty, onAdd, onRemove, onOpen, expanded, onToggle }) {
  const noStock = item.cantidad === 0;
  const stockBajo = item.cantidad > 0 && item.cantidad <= 2;
  const selected = qty > 0;
  const reachedMax = qty >= item.cantidad;
  const initials = useMemo(() => {
    const parts = item.name.split(/\s+/);
    return parts.slice(1, 3).map((p) => p[0]).join("").toUpperCase() || "—";
  }, [item.name]);

  // Top 4 specs from the category default — illustrative until each item
  // ships its own specs[]. In production these are item.specs.
  const topSpecs = (item.specs || defaultSpecsFor(item)).slice(0, 4);
  // Kit categories (cameras / lights / audio) ship multi-item bundles in
  // the codebase via KitEditor. For these we surface "Incluye" first.
  const isKit = ["Cámaras", "Iluminación", "Audio"].includes(item.category);
  const kit = isKit ? (item.kit || defaultKitFor(item)) : null;

  return (
    <article className={"eq-row" + (selected ? " selected" : "") + (noStock ? " sin-stock" : "") + (expanded ? " expanded" : "")}>
      <div className="eq-row-head" onClick={onToggle}>
        <div className="thumb">
          <div className="ph">{initials}</div>
        </div>
        <div className="meta">
          <div className="name">{item.name}</div>
          <div className="sub">
            <span>{item.brand}</span>
            <span>·</span>
            <span>{item.category}</span>
          </div>
        </div>
        <div className="price-block">
          <span className="price">{formatARS(item.pricePerDay)}</span>
          <span className="per">por jornada</span>
          <span className={"stock-row " + (noStock ? "out" : stockBajo ? "low" : "")}>
            {noStock ? "Sin stock" : `${item.cantidad} disp.`}
          </span>
        </div>
        <div className="row-actions-wrap" onClick={(e) => e.stopPropagation()}>
          {qty === 0 ? (
            <button
              className="add-pill"
              onClick={() => !noStock && onAdd(item.id)}
              disabled={noStock}
              aria-label="Agregar"
            >
              <IconPlus size={14}/>
            </button>
          ) : (
            <div className="qty">
              <button onClick={() => onRemove(item.id)} aria-label="Quitar uno"><IconMinus size={14}/></button>
              <span className="num">{qty}</span>
              <button onClick={() => !reachedMax && onAdd(item.id)} disabled={reachedMax} aria-label="Sumar uno">
                <IconPlus size={14}/>
              </button>
            </div>
          )}
          <button className="chev" onClick={onToggle} aria-label={expanded ? "Cerrar" : "Abrir"}>
            <IconChevDown size={14} style={{ transform: expanded ? "rotate(180deg)" : "none", transition: "transform .15s" }}/>
          </button>
        </div>
      </div>

      {expanded && (
        <div className="eq-row-body">
          {isKit && kit && (
            <div className="row-block">
              <div className="row-block-label">Incluye</div>
              <ul className="row-kit">
                {kit.map((it, i) => (
                  <li key={i}>
                    <IconCheck size={12}/>
                    <span style={{flex: 1}}>{it.label}</span>
                    <span className="qty-tag">×{it.qty}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="row-block">
            <div className="row-block-label">Especificaciones</div>
            <dl className="row-specs">
              {topSpecs.map(([k, v]) => (
                <div className="kv" key={k}>
                  <dt>{k}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
          </div>
          <button
            className="see-ficha"
            onClick={(e) => { e.stopPropagation(); onOpen && onOpen(item.id); }}
          >
            Ver ficha completa <IconArrowRight size={12}/>
          </button>
        </div>
      )}
    </article>
  );
}

// ── List view (manages expansion state) ──────────────────────────────
function ListView({ items, cart, onAdd, onRemove, onOpen }) {
  const [expandedId, setExpandedId] = useState(null);
  if (items.length === 0) {
    return (
      <div className="section">
        <div style={{
          background: "var(--surface)", border: "1px solid var(--hairline)",
          borderRadius: 12, padding: "44px 24px", textAlign: "center",
        }}>
          <div style={{fontFamily: "var(--font-sans)", fontWeight: 600, fontSize: 20, color: "var(--muted-foreground)"}}>Sin resultados</div>
          <div style={{marginTop: 6, color: "var(--muted-foreground)", fontSize: 13}}>Probá con otra categoría, marca o término de búsqueda.</div>
        </div>
      </div>
    );
  }
  return (
    <section className="section">
      <div style={{display: "flex", flexDirection: "column", gap: 6}}>
        {items.map((item) => (
          <EquipmentRow
            key={item.id}
            item={item}
            qty={cart[item.id] || 0}
            onAdd={onAdd}
            onRemove={onRemove}
            onOpen={onOpen}
            expanded={expandedId === item.id}
            onToggle={() => setExpandedId(expandedId === item.id ? null : item.id)}
          />
        ))}
      </div>
    </section>
  );
}

function IconChevDown({ size = 14, ...rest }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...rest}>
      <path d="m6 9 6 6 6-6"/>
    </svg>
  );
}

// ── Ficha (equipment detail page) ────────────────────────────────────
function Ficha({ item, qty, onAdd, onRemove, onBack, jornadas }) {
  const noStock = item.cantidad === 0;
  const stockBajo = item.cantidad > 0 && item.cantidad <= 2;
  const reachedMax = qty >= item.cantidad;
  const initials = item.name.split(/\s+/).slice(1, 3).map(p => p[0]).join("").toUpperCase();
  const total = item.pricePerDay * Math.max(1, qty || 1) * jornadas;

  // Fake specs + kit per category — illustrative only.
  const specs = item.specs || defaultSpecsFor(item);
  const kit = item.kit || defaultKitFor(item);

  return (
    <div>
      <div className="ficha-back">
        <a href="#" onClick={(e) => { e.preventDefault(); onBack(); }}>
          <IconArrowLeft /> <span>Volver al catálogo</span>
        </a>
      </div>
      <div className="ficha">
        <div>
          <div className="photo-block">
            {item.isNew && <div className="badge-new"><IconSparkles size={10}/> nuevo</div>}
            <div className="ph">{initials}</div>
          </div>
          <div className="thumbs">
            <div className="thumb active">01</div>
            <div className="thumb">02</div>
            <div className="thumb">03</div>
            <div className="thumb">04</div>
          </div>
        </div>
        <div className="col-right">
          <div>
            <div className="cat-eyebrow">{item.brand} · {item.category}</div>
            <h1 className="title">{item.name}</h1>
            <p className="desc">
              {item.description || `Equipo profesional disponible para producciones audiovisuales en Mar del Plata. Te lo dejamos listo para retirar — consultá disponibilidad por las fechas que necesites.`}
            </p>
          </div>

          <div className="price-card">
            <div className="priceRow">
              <div>
                <div className="label" style={{marginBottom: 4}}>Tarifa diaria</div>
                <span className="price">{formatARS(item.pricePerDay)}</span>
                <span className="per" style={{marginLeft: 8}}>por jornada</span>
              </div>
              <div className={"stock-line" + (noStock ? " out" : stockBajo ? " low" : "")}>
                <span className="dot"></span>
                {noStock ? "Sin stock" : `${item.cantidad} disp.`}
              </div>
            </div>
            <div className="total-row">
              <span>Total · {jornadas} {jornadas === 1 ? "jornada" : "jornadas"}</span>
              <span className="v">{formatARS(total)}</span>
            </div>
            <div className="actionRow">
              {qty === 0 ? (
                <button
                  className="add-cta"
                  onClick={() => !noStock && onAdd(item.id)}
                  disabled={noStock}
                >
                  <IconShoppingBag size={16}/> Agregar al pedido
                </button>
              ) : (
                <>
                  <div className="qty">
                    <button onClick={() => onRemove(item.id)}><IconMinus size={14}/></button>
                    <span className="n">{qty}</span>
                    <button onClick={() => !reachedMax && onAdd(item.id)} disabled={reachedMax}><IconPlus size={14}/></button>
                  </div>
                  <button className="add-cta" style={{flex: 1}} onClick={onBack}>
                    Seguir armando pedido
                  </button>
                </>
              )}
            </div>
          </div>

          <div className="specs-block">
            <h3>Ficha técnica</h3>
            <div className="specs">
              {specs.map(([k, v]) => (
                <div className="row" key={k}>
                  <span className="k">{k}</span>
                  <span className="v">{v}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="kit-block">
            <h3>Incluye</h3>
            <ul className="kit-list">
              {kit.map((it, i) => (
                <li key={i}>
                  <IconCheck size={14}/>
                  <span style={{flex: 1}}>{it.label}</span>
                  <span className="qty-tag">×{it.qty}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {/* Mobile sticky add CTA */}
      <div className="mobile-sticky-cta">
        <div style={{flex: 1, display: "flex", flexDirection: "column", gap: 1}}>
          <span style={{fontFamily: "var(--font-sans)", fontWeight: 600, fontSize: 15, color: "var(--ink)"}}>{formatARS(item.pricePerDay)}</span>
          <span style={{fontFamily: "var(--font-mono)", fontSize: 9, letterSpacing: "0.2em", textTransform: "uppercase", color: "var(--muted-foreground)"}}>por jornada</span>
        </div>
        {qty === 0 ? (
          <button onClick={() => !noStock && onAdd(item.id)} disabled={noStock}
            style={{padding: "12px 22px", borderRadius: 9999, background: "var(--ink)", color: "var(--background)", border: 0, fontFamily: "var(--font-sans)", fontWeight: 600, fontSize: 14, cursor: "pointer"}}
          >Agregar</button>
        ) : (
          <div className="qty" style={{margin: 0}}>
            <button onClick={() => onRemove(item.id)}><IconMinus size={14}/></button>
            <span className="num">{qty}</span>
            <button onClick={() => !reachedMax && onAdd(item.id)} disabled={reachedMax}><IconPlus size={14}/></button>
          </div>
        )}
      </div>
    </div>
  );
}

function defaultSpecsFor(item) {
  const cat = item.category;
  if (cat === "Cámaras") return [
    ["Sensor", "Full-Frame CMOS"], ["Resolución", "4K 60p / FHD 120p"],
    ["Montura", "E-mount"], ["ISO", "80–409.600"],
    ["Codecs", "XAVC S-I, ProRes RAW"], ["Peso", "0,64 kg"],
  ];
  if (cat === "Lentes") return [
    ["Distancia focal", "24–70mm"], ["Apertura máx.", "f/2.8"],
    ["Montura", "Sony E"], ["Filtro", "82mm"],
    ["Distancia mín.", "0,38 m"], ["Peso", "0,69 kg"],
  ];
  if (cat === "Iluminación") return [
    ["Potencia", "600 W"], ["Temp. color", "2700–6500 K (bicolor)"],
    ["CRI", "≥ 96"], ["Atenuación", "0–100%"],
    ["Reflector", "Bowens"], ["Peso", "9,8 kg"],
  ];
  if (cat === "Audio") return [
    ["Patrón", "Súper-cardioide"], ["Respuesta", "40 Hz – 20 kHz"],
    ["Conector", "XLR-3"], ["SPL máx.", "130 dB"],
    ["Peso", "0,17 kg"], ["Alim.", "Phantom +48V"],
  ];
  return [
    ["Categoría", item.category], ["Marca", item.brand], ["Peso", "—"], ["Material", "—"],
  ];
}

function defaultKitFor(item) {
  const cat = item.category;
  if (cat === "Cámaras") return [
    { label: "Cuerpo de cámara", qty: 1 },
    { label: "Batería NP-FZ100", qty: 2 },
    { label: "Cargador dual", qty: 1 },
    { label: "Tapa de cuerpo + correa", qty: 1 },
    { label: "Tarjeta CFexpress 320 GB", qty: 1 },
  ];
  if (cat === "Lentes") return [
    { label: "Lente", qty: 1 },
    { label: "Tapa frontal + trasera", qty: 1 },
    { label: "Parasol original", qty: 1 },
    { label: "Estuche acolchado", qty: 1 },
  ];
  if (cat === "Iluminación") return [
    { label: "Cabezal LED", qty: 1 },
    { label: "Fuente + cable IEC", qty: 1 },
    { label: "Reflector Bowens 55°", qty: 1 },
    { label: "Control remoto", qty: 1 },
    { label: "Bolso de transporte", qty: 1 },
  ];
  if (cat === "Audio") return [
    { label: "Micrófono", qty: 1 },
    { label: "Pistola + windscreen", qty: 1 },
    { label: "Cable XLR 5m", qty: 1 },
    { label: "Caja Pelican", qty: 1 },
  ];
  return [{ label: "Equipo principal", qty: 1 }, { label: "Estuche", qty: 1 }];
}

// IconArrowLeft is missing from icons.jsx — define inline
function IconArrowLeft({ size = 12 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 12H5M12 19l-7-7 7-7"/>
    </svg>
  );
}

// ── Cart mini bar (fixed bottom) ─────────────────────────────────────
function CartMiniBar({ cart, equipment, jornadas, onOpen }) {
  const entries = Object.entries(cart).filter(([, q]) => q > 0);
  const count = entries.reduce((a, [, q]) => a + q, 0);
  const perDay = entries.reduce((acc, [id, qty]) => {
    const item = equipment.find((e) => e.id === id);
    return item ? acc + item.pricePerDay * qty : acc;
  }, 0);
  const total = perDay * jornadas;
  const isEmpty = count === 0;
  return (
    <div className="cart-mini-bar">
      <div className="cmb-left">
        <div className="cmb-icon">
          <IconShoppingBag size={16} />
          {!isEmpty && <span className="cmb-badge">{count}</span>}
        </div>
        <div className="cmb-lead">
          <div className="title">{isEmpty ? "Carrito vacío" : `${count} ${count === 1 ? "ítem" : "ítems"}`}</div>
          <div className="sub">{isEmpty ? "Sumá equipos" : `${jornadas} ${jornadas === 1 ? "jornada" : "jornadas"}`}</div>
        </div>
      </div>
      <div className="cmb-totals">
        <div className="sub">Total</div>
        <div className="total">{formatARS(total)}</div>
      </div>
      <button
        className="cmb-cta"
        onClick={onOpen}
        disabled={isEmpty}
      >
        Ver carrito
      </button>
    </div>
  );
}

Object.assign(window, { CartMiniBar });
Object.assign(window, {
  TopBar, Hero, SubToolbar, CategoryMosaic, BrandRow,
  EquipmentCard, CategoryCarousel, Footer, CartDrawer,
  EquipmentRow, ListView, Ficha, IconArrowLeft,
});
