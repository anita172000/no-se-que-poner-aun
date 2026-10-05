# 2. Oferta y precios

## Nombre de la oferta: "Sistema de Conversión 24/7"
> Respondemos a cada lead en menos de 60 segundos, día y noche, lo calificamos y lo dejamos con cita en tu agenda.
> Si en 60 días no te genera al menos el doble de tu cuota en citas atribuibles, trabajamos gratis hasta conseguirlo.

## Componentes (todos incluidos en este repositorio)
| Módulo | Qué hace | Archivo |
|---|---|---|
| Recepcionista IA 24/7 | Chat web/WhatsApp que responde, califica, puntúa y reserva | `app/agents/recepcionista.py`, `app/static/widget.js` |
| Captura de leads | Webhook para formularios, Meta Lead Ads, Zapier/Make | `POST /api/leads` |
| Seguimiento automático | Secuencias para leads sin cita, presupuestos y no-shows | `app/agents/seguimiento.py` |
| Reactivación de base de datos | Mensajes personalizados a antiguos clientes | `app/agents/reactivacion.py` |
| Reseñas | Respuesta a reseñas y petición tras la cita | `app/agents/resenas.py` |
| Panel de resultados | KPIs, leads, citas y seguimientos del día | `/panel` |

## Planes
| Plan | Setup | Mensual | Incluye |
|---|---|---|---|
| **Arranque** | 997 € | 497 € | Recepcionista IA web + WhatsApp, agenda, CRM, informe mensual |
| **Crecimiento** (recomendado) | 1.997 € | 997 € | Arranque + seguimiento + no-shows + reseñas + 1 reactivación/trimestre |
| **Dominio** | 3.997 € | 1.997 € | Crecimiento + voz IA para llamadas + multi-sede + anuncios + reunión semanal |

Permanencia mínima: 3 meses. Pago del setup por adelantado; cuota mensual domiciliada.

## Oferta de entrada (para conseguir los primeros clientes): Reactivación a éxito
- **0 € por adelantado.** Cobras **50-100 € por cita asistida** (o el 10-15 % del primer tratamiento).
- Necesitas: el CSV de pacientes con consentimiento y una oferta de la clínica.
- Ejecución: `python cli.py reactivar <cliente> pacientes.csv --campana "otoño"`.
- Resultado típico de una base de 1.000 contactos: 3-8 % responde, 1-3 % agenda → 10-30 citas.
- Al entregar resultados, ofreces el plan Crecimiento: "esto lo hicimos con tus pacientes antiguos; imagina con cada lead nuevo".

## Complementos (upsells)
- Voz IA para llamadas entrantes/perdidas: +300-600 €/mes.
- Gestión de Meta/Google Ads: +500 €/mes + inversión.
- Sedes adicionales: +50 % de la cuota por sede.
- Reactivación extra: 497 € por campaña o modelo a éxito.

## Garantía
Si en 60 días el sistema no genera citas atribuibles por valor ≥ 2× la cuota mensual, seguimos trabajando sin cobrar la cuota hasta lograrlo.
La atribución se mide en el panel (leads y citas creados por el sistema).
