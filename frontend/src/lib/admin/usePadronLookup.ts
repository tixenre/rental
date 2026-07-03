/**
 * usePadronLookup — autocompletar razón social/nombre/apellido/domicilio/
 * condición IVA desde el padrón de ARCA a partir de un CUIT. Comodidad de
 * carga: si AFIP no responde o el CUIT no tiene datos, no rompe nada — solo
 * no autocompleta.
 *
 * `nombre`/`apellido` solo vienen poblados para una persona física sin razón
 * social propia (AFIP los da separados) — útil para un formulario con esos
 * dos campos separados (cliente); uno con un solo campo de identidad
 * (emisor, siempre una identidad de negocio) usa `razon_social`.
 */
import { useState } from "react";

import { facturacionApi } from "@/lib/admin/api";

export type PadronDatos = {
  razon_social: string;
  nombre: string;
  apellido: string;
  domicilio: string;
  condicion_iva: string;
};

export function usePadronLookup(onFound: (datos: PadronDatos) => void) {
  const [buscando, setBuscando] = useState(false);
  const [noEncontrado, setNoEncontrado] = useState(false);
  // CUIT encontrado pero dado de baja en AFIP — aviso, no bloquea nada
  // (el dueño decide si igual quiere seguir).
  const [inactivo, setInactivo] = useState(false);
  // Distinto de noEncontrado: no pudimos ni completar la consulta (WSAA no
  // autoriza, relación no delegada, cert vencido, red) — el motivo real de
  // ARCA/nuestro lado, no "ARCA no tiene datos para este CUIT" (que sería
  // engañoso acá).
  const [motivo, setMotivo] = useState<string | null>(null);

  const buscar = async (cuit: string) => {
    const digits = cuit.replace(/\D/g, "");
    if (digits.length !== 11) return;
    setBuscando(true);
    setNoEncontrado(false);
    setInactivo(false);
    setMotivo(null);
    try {
      const result = await facturacionApi.consultarPadron(digits);
      if (result.encontrado) {
        onFound({
          razon_social: result.razon_social,
          nombre: result.nombre,
          apellido: result.apellido,
          domicilio: result.domicilio,
          condicion_iva: result.condicion_iva,
        });
        setInactivo(!!result.estado_clave && result.estado_clave !== "ACTIVO");
      } else if (result.motivo) {
        setMotivo(result.motivo);
      } else {
        setNoEncontrado(true);
      }
    } catch (e) {
      // El route de consultar_padron nunca debería tirar (atrapa RuntimeError
      // y devuelve {encontrado:false, motivo} en un 200) — si esto se
      // dispara, es un 500/red real que se estaba perdiendo en un genérico
      // "sin datos", exactamente lo que este hook existe para evitar.
      // `authedJson` ya arma el mensaje real (método/ruta/status/detalle).
      setMotivo(e instanceof Error ? e.message : "Error inesperado consultando ARCA");
    } finally {
      setBuscando(false);
    }
  };

  return { buscar, buscando, noEncontrado, inactivo, motivo };
}
