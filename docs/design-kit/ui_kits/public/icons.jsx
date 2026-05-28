/* Inline SVG icons — lucide-react equivalents.
 * Stroke 2, currentColor. Lift these freely.
 */
const stroke = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

function Icon({ children, size = 16, ...rest }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...stroke} {...rest}>
      {children}
    </svg>
  );
}

const IconCalendar = (p) => (
  <Icon {...p}>
    <rect x="3" y="4" width="18" height="18" rx="2" />
    <path d="M16 2v4M8 2v4M3 10h18" />
  </Icon>
);
const IconShoppingBag = (p) => (
  <Icon {...p}>
    <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z" />
    <path d="M3 6h18M16 10a4 4 0 0 1-8 0" />
  </Icon>
);
const IconUser = (p) => (
  <Icon {...p}>
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </Icon>
);
const IconSearch = (p) => (
  <Icon {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="m21 21-4.3-4.3" />
  </Icon>
);
const IconGrid = (p) => (
  <Icon {...p}>
    <rect x="3" y="3" width="7" height="7" />
    <rect x="14" y="3" width="7" height="7" />
    <rect x="3" y="14" width="7" height="7" />
    <rect x="14" y="14" width="7" height="7" />
  </Icon>
);
const IconList = (p) => (
  <Icon {...p}>
    <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" />
  </Icon>
);
const IconPlus = (p) => (
  <Icon {...p}>
    <path d="M12 5v14M5 12h14" />
  </Icon>
);
const IconMinus = (p) => (
  <Icon {...p}>
    <path d="M5 12h14" />
  </Icon>
);
const IconCheck = (p) => (
  <Icon {...p}>
    <path d="M20 6 9 17l-5-5" />
  </Icon>
);
const IconX = (p) => (
  <Icon {...p}>
    <path d="M18 6 6 18M6 6l12 12" />
  </Icon>
);
const IconArrowRight = (p) => (
  <Icon {...p}>
    <path d="M5 12h14M12 5l7 7-7 7" />
  </Icon>
);
const IconSparkles = (p) => (
  <Icon {...p}>
    <path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z" />
  </Icon>
);
const IconMessage = (p) => (
  <Icon {...p}>
    <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
  </Icon>
);
const IconMapPin = (p) => (
  <Icon {...p}>
    <path d="M20 10c0 7-8 13-8 13s-8-6-8-13a8 8 0 0 1 16 0Z" />
    <circle cx="12" cy="10" r="3" />
  </Icon>
);
const IconPhone = (p) => (
  <Icon {...p}>
    <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
  </Icon>
);
const IconMail = (p) => (
  <Icon {...p}>
    <rect x="2" y="4" width="20" height="16" rx="2" />
    <path d="m22 7-10 6L2 7" />
  </Icon>
);
const IconClock = (p) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="10" />
    <path d="M12 6v6l4 2" />
  </Icon>
);
const IconInstagram = (p) => (
  <Icon {...p}>
    <rect x="2" y="2" width="20" height="20" rx="5" />
    <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37zM17.5 6.5h.01" />
  </Icon>
);

/* ── Category illustrations (the brand's hand-drawn set) ───────────── */
const illBase = {
  viewBox: "0 0 64 64",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2.5,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

const IllCamara = () => (
  <svg {...illBase}>
    <rect x="6" y="22" width="30" height="22" rx="3" />
    <circle cx="14" cy="16" r="4" />
    <circle cx="24" cy="16" r="4" />
    <path d="M14 20v2M24 20v2" />
    <rect x="36" y="27" width="18" height="12" rx="2" />
    <circle cx="45" cy="33" r="3" />
    <path d="M10 48l4 6M32 48l-4 6" />
  </svg>
);
const IllLente = () => (
  <svg {...illBase}>
    <rect x="8" y="20" width="48" height="24" rx="3" />
    <path d="M16 20v24M22 20v24M44 20v24M50 20v24" />
    <circle cx="32" cy="32" r="6" />
    <path d="M30 30l1.5 1.5" />
  </svg>
);
const IllLuz = () => (
  <svg {...illBase}>
    <rect x="14" y="10" width="30" height="20" rx="3" />
    <path d="M20 16h18M20 20h18M20 24h18" />
    <path d="M44 14l8 4M44 26l8-4" />
    <path d="M29 30v6M29 36l-8 18M29 36l8 18M29 36h-2M29 36h2" />
  </svg>
);
const IllAudio = () => (
  <svg {...illBase}>
    <rect x="6" y="20" width="30" height="14" rx="7" />
    <path d="M10 20v14M14 20v14M18 20v14M22 20v14M26 20v14M30 20v14" />
    <rect x="36" y="24" width="10" height="6" rx="1.5" />
    <path d="M46 27h6" />
    <path d="M50 24v6" />
    <path d="M52 18v18" />
  </svg>
);
const IllSilla = () => (
  <svg {...illBase}>
    <path d="M16 14h32" />
    <path d="M16 18h32" />
    <path d="M14 32h36" />
    <path d="M16 14l16 38M48 14L32 52" />
    <path d="M16 52l16-38M48 52L32 14" />
    <path d="M14 52h36" />
  </svg>
);
const IllClaqueta = () => (
  <svg {...illBase}>
    <path d="M8 18l44-6 2 8-44 6z" />
    <path d="M14 14l-2 6M22 13l-2 6M30 12l-2 6M38 11l-2 6M46 10l-2 6" />
    <rect x="8" y="26" width="48" height="26" rx="2" />
    <path d="M14 34h12M14 40h20M14 46h16" />
  </svg>
);
const IllCable = () => (
  <svg {...illBase}>
    <rect x="4" y="26" width="14" height="12" rx="2" />
    <circle cx="9" cy="32" r="1" />
    <circle cx="13" cy="30" r="1" />
    <circle cx="13" cy="34" r="1" />
    <path d="M18 32c8 0 8 14 16 14s8-14 16-14" />
    <rect x="46" y="26" width="14" height="12" rx="2" />
    <circle cx="51" cy="32" r="1" />
    <circle cx="55" cy="30" r="1" />
    <circle cx="55" cy="34" r="1" />
  </svg>
);

const CATEGORY_ILLS = {
  "Cámaras": IllCamara,
  "Lentes": IllLente,
  "Iluminación": IllLuz,
  "Audio": IllAudio,
  "Soportes": IllSilla,
  "Accesorios": IllClaqueta,
  "Adaptadores": IllCable,
};

Object.assign(window, {
  Icon,
  IconCalendar, IconShoppingBag, IconUser, IconSearch,
  IconGrid, IconList, IconPlus, IconMinus, IconCheck, IconX,
  IconArrowRight, IconSparkles, IconMessage,
  IconMapPin, IconPhone, IconMail, IconClock, IconInstagram,
  CATEGORY_ILLS,
});
