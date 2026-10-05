# 5. Onboarding y entrega (SOP de 14 días)

## Día 0 — Firma
- [ ] Contrato firmado (`docs/06-contrato-plantilla.md`) y setup cobrado.
- [ ] Contrato de encargado del tratamiento (RGPD) firmado.
- [ ] Grupo de WhatsApp/Slack con el cliente y kickoff agendado en 48 h.

## Días 1-3 — Kickoff y ficha
- [ ] Reunión de 45 min: servicios, precios "desde", horarios, políticas, FAQ, tono, oferta vigente.
- [ ] Crear `clientes/<id>.json` copiando `clientes/clinica-lumiere.json`.
- [ ] El cliente valida la ficha por escrito (la IA solo dice lo que hay en ella).

## Días 4-7 — Instalación
- [ ] Despliegue (Docker) o alta del cliente en el servidor compartido.
- [ ] Widget en su web: `<script src="https://TU-DOMINIO/static/widget.js" data-cliente="<id>" data-color="#..."></script>`
- [ ] Formularios y Meta Lead Ads → `POST /api/leads` (vía Zapier/Make o webhook directo).
- [ ] WhatsApp Business API (proveedor: 360dialog, Twilio o Meta Cloud API) reenviando mensajes a `POST /api/chat` con `canal: "whatsapp"`.
- [ ] Enlace de reseñas de Google en la ficha.

## Días 8-10 — Pruebas
- [ ] 30 conversaciones de prueba: precios, cita, cambio de cita, queja, urgencia, pregunta fuera de ficha, petición de humano.
- [ ] Revisar cada conversación en la base de datos; ajustar ficha/FAQ.
- [ ] El cliente prueba la demo y da el OK.

## Días 11-14 — Lanzamiento
- [ ] Activar en producción. Avisar al equipo del cliente de cómo llegan los escalados.
- [ ] Lanzar la primera campaña de reactivación (plan Crecimiento).
- [ ] Enviar al cliente el enlace del panel.

## Mantenimiento mensual (2-3 h por cliente)
- [ ] Revisar 20 conversaciones al azar y todas las escaladas.
- [ ] Actualizar oferta del mes y FAQ.
- [ ] Informe mensual: leads, tiempo de respuesta, citas, conversión, ingresos atribuidos (datos de `/api/metricas`).
- [ ] Reunión de 20 min: resultados + siguiente mejora (upsell).
