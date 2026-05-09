/** Formatea pesos argentinos: 97500 → "$97.500,00" */
export const formatARS = (n: number) =>
  "$" +
  new Intl.NumberFormat("es-AR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n);
