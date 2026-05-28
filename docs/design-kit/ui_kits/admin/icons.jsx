/* Admin icons — reuse lucide style.
 * Different selection than the public side (more chrome icons). */
const adminStroke = { fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round" };
function AIcon({ children, size = 16, ...rest }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" {...adminStroke} {...rest}>{children}</svg>;
}

const ALayoutDashboard = (p) => <AIcon {...p}><rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/></AIcon>;
const APackage = (p) => <AIcon {...p}><path d="m16.5 9.4-9-5.19M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><path d="M3.27 6.96 12 12.01l8.73-5.05M12 22.08V12"/></AIcon>;
const AClipboard = (p) => <AIcon {...p}><rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M9 14h6M9 18h4"/></AIcon>;
const AUsers = (p) => <AIcon {...p}><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></AIcon>;
const AChart = (p) => <AIcon {...p}><path d="M3 3v18h18"/><path d="M18 9l-5 5-4-4-3 3"/></AIcon>;
const ASettings = (p) => <AIcon {...p}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33 1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82 1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></AIcon>;
const APalette = (p) => <AIcon {...p}><circle cx="13.5" cy="6.5" r=".5"/><circle cx="17.5" cy="10.5" r=".5"/><circle cx="8.5" cy="7.5" r=".5"/><circle cx="6.5" cy="12.5" r=".5"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.83 0 1.5-.67 1.5-1.5 0-.39-.15-.74-.39-1.01-.23-.26-.38-.61-.38-.99 0-.83.67-1.5 1.5-1.5H16c3.31 0 6-2.69 6-6 0-4.97-4.5-9-10-9z"/></AIcon>;
const ASparkles = (p) => <AIcon {...p}><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/></AIcon>;
const ALogOut = (p) => <AIcon {...p}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5M21 12H9"/></AIcon>;
const AChevronRight = (p) => <AIcon {...p}><path d="m9 18 6-6-6-6"/></AIcon>;
const AList = (p) => <AIcon {...p}><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></AIcon>;
const AFolderTree = (p) => <AIcon {...p}><path d="M22 11v3a1 1 0 0 1-1 1H6.83a2 2 0 0 1-1.41-.59l-.83-.82A2 2 0 0 0 3.17 13H2.5"/><path d="M22 4v3a1 1 0 0 1-1 1H6.83a2 2 0 0 1-1.41-.59l-.83-.82A2 2 0 0 0 3.17 6H2.5"/><circle cx="14" cy="20" r="2"/><path d="M14 18v-3a2 2 0 0 0-2-2H8"/></AIcon>;
const ABuilding = (p) => <AIcon {...p}><rect x="4" y="2" width="16" height="20" rx="2"/><path d="M9 22v-4h6v4M8 6h.01M16 6h.01M12 6h.01M12 10h.01M12 14h.01M16 10h.01M16 14h.01M8 10h.01M8 14h.01"/></AIcon>;
const ATag = (p) => <AIcon {...p}><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></AIcon>;
const AWrench = (p) => <AIcon {...p}><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></AIcon>;
const ASearch = (p) => <AIcon {...p}><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></AIcon>;
const APlus = (p) => <AIcon {...p}><path d="M12 5v14M5 12h14"/></AIcon>;
const AFilter = (p) => <AIcon {...p}><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></AIcon>;
const AEye = (p) => <AIcon {...p}><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></AIcon>;
const AEyeOff = (p) => <AIcon {...p}><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><path d="M2 2l20 20"/></AIcon>;
const ATrash = (p) => <AIcon {...p}><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></AIcon>;
const APencil = (p) => <AIcon {...p}><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z"/></AIcon>;
const AMore = (p) => <AIcon {...p}><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></AIcon>;
const AArrowUp = (p) => <AIcon {...p}><path d="M5 12l7-7 7 7M12 5v14"/></AIcon>;
const AArrowDown = (p) => <AIcon {...p}><path d="M19 12l-7 7-7-7M12 19V5"/></AIcon>;
const AX = (p) => <AIcon {...p}><path d="M18 6 6 18M6 6l12 12"/></AIcon>;
const ACheck = (p) => <AIcon {...p}><path d="M20 6 9 17l-5-5"/></AIcon>;

Object.assign(window, {
  ALayoutDashboard, APackage, AClipboard, AUsers, AChart, ASettings,
  APalette, ASparkles, ALogOut, AChevronRight, AList, AFolderTree,
  ABuilding, ATag, AWrench, ASearch, APlus, AFilter, AEye, AEyeOff,
  ATrash, APencil, AMore, AArrowUp, AArrowDown, AX, ACheck,
});
