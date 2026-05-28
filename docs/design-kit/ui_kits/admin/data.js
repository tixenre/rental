/* Admin back-office — fake data approximating the inventory schema. */
const ADMIN_EQUIPMENT = [
  { id: 1,  name: "FX3 Cinema Line",         brand: "Sony",      cat: "Cámaras",     stock: 2, price: 38000, roiPct: 7.6, state: "visible",    new: true,  tags: ["destacado", "estrella"] },
  { id: 2,  name: "A7S III",                 brand: "Sony",      cat: "Cámaras",     stock: 3, price: 28000, roiPct: 6.2, state: "visible",    new: false, tags: ["full-frame"] },
  { id: 3,  name: "C70 Cinema EOS",          brand: "Canon",     cat: "Cámaras",     stock: 1, price: 32000, roiPct: 5.4, state: "visible",    new: false, tags: ["super35"] },
  { id: 4,  name: "R5 C",                    brand: "Canon",     cat: "Cámaras",     stock: 2, price: 30000, roiPct: 4.8, state: "incomplete", new: true,  tags: ["8k"] },
  { id: 5,  name: "X-H2S",                   brand: "Fujifilm",  cat: "Cámaras",     stock: 0, price: 22000, roiPct: 3.1, state: "hidden",     new: false, tags: [] },
  { id: 6,  name: "Ronin 4D",                brand: "DJI",       cat: "Cámaras",     stock: 1, price: 56000, roiPct: 9.2, state: "visible",    new: false, tags: ["gimbal", "destacado"] },
  { id: 7,  name: "G Master 24-70 f/2.8 II", brand: "Sony",      cat: "Lentes",      stock: 2, price: 18000, roiPct: 5.7, state: "visible",    new: false, tags: ["e-mount"] },
  { id: 8,  name: "G Master 70-200 f/2.8",   brand: "Sony",      cat: "Lentes",      stock: 2, price: 22000, roiPct: 6.0, state: "visible",    new: false, tags: ["e-mount"] },
  { id: 9,  name: "RF 24-70 f/2.8 L",        brand: "Canon",     cat: "Lentes",      stock: 2, price: 17500, roiPct: 5.2, state: "visible",    new: false, tags: ["rf-mount"] },
  { id: 10, name: "RF 50 f/1.2 L",           brand: "Canon",     cat: "Lentes",      stock: 1, price: 15000, roiPct: 4.4, state: "visible",    new: true,  tags: ["rf-mount", "prime"] },
  { id: 11, name: "Aputure 600x Pro",        brand: "Aputure",   cat: "Iluminación", stock: 0, price: 18000, roiPct: 2.1, state: "maintenance", new: false, tags: ["bicolor"] },
  { id: 12, name: "Aputure 300d Mark II",    brand: "Aputure",   cat: "Iluminación", stock: 3, price: 9500,  roiPct: 4.9, state: "visible",    new: false, tags: ["daylight"] },
  { id: 13, name: "MKH 416 Shotgun",         brand: "Sennheiser",cat: "Audio",       stock: 2, price: 11000, roiPct: 6.8, state: "visible",    new: false, tags: ["mic"] },
  { id: 14, name: "Wireless Pro · kit",      brand: "Rode",      cat: "Audio",       stock: 3, price: 6500,  roiPct: 5.5, state: "visible",    new: true,  tags: ["lavalier"] },
  { id: 15, name: "FSB 8 + trípode",         brand: "Sachtler",  cat: "Soportes",    stock: 2, price: 8500,  roiPct: 3.8, state: "visible",    new: false, tags: ["fluid-head"] },
  { id: 16, name: "Ronin RS3 Pro",           brand: "DJI",       cat: "Soportes",    stock: 1, price: 9500,  roiPct: 4.2, state: "visible",    new: false, tags: ["gimbal"] },
];

Object.assign(window, { ADMIN_EQUIPMENT });
