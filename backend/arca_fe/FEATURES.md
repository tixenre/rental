# Qué podés hacer con `arca_fe`

Esta página es para vos si estás evaluando si `arca_fe` te sirve para facturar electrónicamente
en Argentina — describe lo que la librería hace **hoy, ya implementado y probado**, en términos de
qué resuelve, no de qué funciones tiene. Para el detalle técnico de instalación y uso, ver el
[`README.md`](README.md).

## Facturación electrónica con CAE, sin pelearte con el WSDL de ARCA

Le pasás los datos del comprobante (emisor, receptor, importes, concepto) y `arca_fe` arma el
pedido en el formato exacto que ARCA espera, lo envía y te devuelve el **CAE** (el número que hace
que la factura sea legalmente válida) junto con su fecha de vencimiento. No necesitás conocer el
protocolo SOAP de AFIP/ARCA ni su formato de fechas/importes — eso lo resuelve la librería.

## Factura A, B o C — automático, según quién factura y a quién

No elegís vos qué letra de factura corresponde: le decís si el emisor es Responsable Inscripto,
Monotributista o Exento, y si el receptor tiene CUIT o no, y `arca_fe` deriva la letra correcta
(A/B/C) sola, siguiendo las reglas oficiales de ARCA. Si en algún caso puntual necesitás forzar un
tipo de comprobante específico (por ejemplo, Factura M o un comprobante de exportación en curso de
implementación en tu propio flujo), también podés indicarlo explícitamente.

## Notas de crédito y de débito

Cuando necesitás anular o corregir una factura ya emitida, `arca_fe` arma la nota de crédito o
débito correspondiente, referenciada correctamente a la factura original — con la misma
verificación de importes y de letra (A/B/C sigue la de la factura que corrige).

## Los centavos cuadran, siempre

El cálculo de neto/IVA/total se hace con precisión decimal exacta (nunca con errores de coma
flotante) y la librería **verifica matemáticamente** que neto + IVA = total antes de mandar
cualquier cosa a ARCA — un comprobante con números que no cierran nunca llega a pedir CAE.

## Múltiples alícuotas de IVA, tributos y percepciones en el mismo comprobante

Si tu operación mezcla productos con distinta alícuota de IVA (21%, 10.5%, 27%, exento), o necesita
sumar percepciones/tributos provinciales o municipales, `arca_fe` arma el comprobante completo con
todos esos ítems desglosados — no estás limitado a "un IVA por factura".

## Facturación en moneda extranjera

Si necesitás facturar en dólares (u otra moneda con código de ARCA), `arca_fe` soporta la
cotización correspondiente en el comprobante.

## Facturación de Crédito Electrónica (FCE / Ley MiPyme)

Para el circuito de factura de crédito electrónica (útil si tu negocio o tus clientes operan bajo
el régimen MiPyme), la librería valida las reglas estructurales específicas que ARCA exige para
este tipo de comprobante (datos de cobro obligatorios, códigos de anulación), para que no se te
escape un comprobante FCE incompleto.

## Consulta de CUIT — como el autocompletar del facturador oficial

Dado un CUIT, `arca_fe` te devuelve la razón social, el domicilio fiscal y la condición ante el IVA
de esa persona o empresa — el mismo dato que ves autocompletarse cuando cargás un CUIT en el
facturador online de ARCA. Útil para no pedirle esos datos a mano a tu cliente, y para detectar un
CUIT mal cargado antes de facturar.

## Validación de CUIT sin llamar a ARCA

Antes de gastar una consulta de red, `arca_fe` valida el formato y el dígito verificador de un CUIT
localmente — un CUIT mal tipeado se detecta al instante, con o sin guiones ("20-30123456-3" o
"20301234563" son lo mismo para la librería).

## El comprobante, listo para mostrar — en 3 formatos distintos, con nombre y descripción

Una vez que tenés el CAE, `arca_fe` te arma el HTML completo del comprobante (para convertir a PDF
con la herramienta que uses, o mostrarlo directo como preview) en **tres formatos**, cada uno con
su nombre y descripción listos para mostrarle a quien elige (`LAYOUTS_INFO`, para armar un
selector real sin inventar copy propio): **Oficial** (réplica del formulario de ARCA, A4, con el
detalle completo de cada ítem), **Detallada** (A4 con diseño propio, mismo nivel de detalle) y
**Simplificada** (formato vertical compacto, mínimo 1080×1350 — pensado para compartir por
WhatsApp o redes — **resume cada ítem a descripción e importe, sin cantidad ni precio unitario**:
si una operación tiene varios productos o cantidades que necesitan ese desglose, la librería
**rechaza** generarla en este formato en vez de mostrar un comprobante incompleto — para eso están
Oficial o Detallada). Incluye el QR fiscal oficial (el mismo que cualquiera puede escanear para
verificar el comprobante contra ARCA) y podés inyectarle tu propia tipografía de marca sin tocar
el layout. ¿Querés ver cómo se ven antes de integrar la librería? `arca_fe.ejemplos` genera una
galería HTML de muestra con datos ficticios (`python -m arca_fe.ejemplos`).

## Documento protegido — no un PDF cualquiera

El documento final se puede proteger para que se pueda ver e imprimir libremente, pero no editar
ni copiarle el texto (para que nadie "levante" un monto o un CUIT con un copy-paste, o edite el
archivo y lo reenvíe como si fuera el original) — y además queda firmado digitalmente, para que
cualquier lector de PDF confirme que el archivo no fue alterado desde que se generó. Opcionalmente
podés sumarle metadatos con los datos fiscales embebidos en el archivo, y un sello de tiempo de una
autoridad externa (RFC 3161) que certifica cuándo se generó.

## Errores que te dicen qué hacer, no solo que algo falló

Cuando algo sale mal, `arca_fe` no te devuelve un error genérico: te dice si fue un problema de
autenticación (revisá tu certificado), de red (probablemente conviene reintentar), un rechazo real
de ARCA por una regla de negocio (ej. un dato mal cargado — no tiene sentido reintentar sin
corregirlo), o una respuesta de ARCA que no se pudo interpretar. Cada categoría es un tipo de error
distinto, para que tu aplicación decida automáticamente qué hacer en cada caso — reintentar,
avisarle al usuario, o abrir un ticket con soporte.

## Reintentos automáticos, configurables

Para las fallas transitorias (una caída momentánea de la red o del servicio de ARCA), `arca_fe`
incluye un mecanismo de reintento con espera creciente entre intentos — opcional, vos decidís
cuándo usarlo y con qué parámetros.

## Pensada para no bloquear tu aplicación

Si tu aplicación es asíncrona (por ejemplo, atiende pedidos web mientras factura), `arca_fe` ofrece
las mismas operaciones (pedir CAE, autenticar, consultar un CUIT) en versión que no bloquea el resto
de tu programa mientras espera la respuesta de ARCA.

## Sin ataduras a ningún framework

`arca_fe` no depende de FastAPI, Django, ni de ningún motor de base de datos — es una librería de
Python pura (más las dos dependencias imprescindibles para hablar SOAP y manejar certificados). La
podés usar en cualquier proyecto Python, no solo en el que la vio nacer.

---

*Esta página describe funcionalidad ya implementada — no es una hoja de ruta. Se actualiza junto
con el código: si una sección de acá no coincide con lo que hace la librería, es un bug de
documentación, avisá.*
