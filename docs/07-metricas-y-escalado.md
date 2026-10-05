# 7. Métricas, cumplimiento y escalado

## KPIs por cliente (panel `/panel`)
| KPI | Objetivo |
|---|---|
| Tiempo de primera respuesta | < 60 s |
| Conversión lead → cita | > 35 % |
| Leads calientes (puntuación ≥ 70) | seguimiento en < 1 h por el equipo |
| Escalados a humano | < 10 % de conversaciones |
| No-shows | < 15 % |
| Ingresos atribuidos / cuota | > 3× |

## KPIs de la agencia
MRR, nº de clientes, churn mensual (< 5 %), CAC, LTV (objetivo LTV/CAC > 5), margen bruto (> 80 %), horas/cliente/mes (< 3).

## Cumplimiento (UE / España)
- **RGPD:** contrato de encargado con cada cliente; solo contactar con base legal; baja sencilla en cada mensaje; datos de salud mínimos.
- **Reglamento Europeo de IA:** informar al usuario de que habla con una IA (añádelo al saludo del widget si el cliente lo prefiere explícito).
- **LSSI:** comunicaciones comerciales solo con consentimiento previo o relación contractual previa.
- **Sanidad:** la IA no diagnostica ni promete resultados (reglas incluidas en el prompt del agente).

## Plan de escalado
1. **0-5 clientes:** tú vendes y entregas. Usa la reactivación a éxito para conseguir casos de éxito y testimonios en vídeo.
2. **5-15 clientes:** contrata un/a responsable de onboarding (sigue `docs/05`). Tú solo vendes.
3. **15-40 clientes:** setter (prospección), closer a comisión (10-15 % del primer año), gestor de cuentas cada 20 clientes.
4. **Producto:** al repetir el nicho, empaqueta como SaaS de marca blanca para otras agencias (149-299 €/mes por cuenta).

## Roadmap técnico sugerido
- Integración nativa con Google Calendar / Doctoralia / software de gestión de la clínica.
- Voz IA para llamadas perdidas (plan Dominio).
- Envío automático de seguimientos vía WhatsApp API programado (cron que llama a `/api/seguimiento`).
- Informe mensual en PDF generado automáticamente.
