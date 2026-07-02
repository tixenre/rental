/**
 * usePadronLookup — autocompletar razón social/domicilio/condición IVA desde
 * el padrón de ARCA a partir de un CUIT. Comodidad de carga: si AFIP no
 * responde o el CUIT no tiene datos, no rompe nada — solo no autocompleta.
 */
import { useState } from "react";

import { facturacionApi } from "@/lib/admin/api";

export type PadronDatos = { razon_social: string; domicilio: string; condicion_iva: string };

export function usePadronLookup(onFound: (datos: PadronDatos) => void) {
  const [buscando, setBuscando] = useState(false);
  const [noEncontrado, setNoEncontrado] = useState(false);

  const buscar = async (cuit: string) => {
    const digits = cuit.replace(/\D/g, "");
    if (digits.length !== 11) return;
    setBuscando(true);
    setNoEncontrado(false);
    try {
      const result = await facturacionApi.consultarPadron(digits);
      if (result.encontrado) {
        onFound({
          razon_social: result.razon_social,
          domicilio: result.domicilio,
          condicion_iva: result.condicion_iva,
        });
      } else {
        setNoEncontrado(true);
      }
    } catch {
      setNoEncontrado(true);
    } finally {
      setBuscando(false);
    }
  };

  return { buscar, buscando, noEncontrado };
}
