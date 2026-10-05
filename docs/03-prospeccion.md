# 3. Prospección: cómo conseguir clientes

## Lista de prospectos (objetivo: 300 negocios/mes)
Fuentes: Google Maps ("clínica estética Madrid"), directorios de colegios profesionales, Meta Ads Library
(negocios que **ya pagan anuncios** = tienen leads y presupuesto), Instagram, LinkedIn.
Filtro ideal: 4,0-4,6★ con más de 50 reseñas, anuncios activos, sin chat ni reserva online, formulario que promete "respuesta en 24-48 h".

## Prueba del "cliente misterioso" (tu arma principal)
1. Rellena su formulario o escribe por Instagram/WhatsApp un martes a las 19:30.
2. Llama el sábado a mediodía.
3. Anota cuánto tardan en responder. Esa cifra abre la conversación.

## Auditoría automática
Pega lo que sabes del negocio en un .txt y ejecuta:
```
python cli.py auditar ejemplos/prospecto_ejemplo.txt --ticket 1500 --leads 80
```
Obtienes: fugas de dinero cuantificadas, gancho personalizado y una secuencia de 4 mensajes lista para enviar.

## Plantillas base
**Email 1 (día 1) — asunto: `vuestro formulario`**
> Hola {nombre}, el martes a las 19:40 pedí información en la web de {clínica}. La respuesta llegó el jueves a las 11:00.
> Para un paciente de ortodoncia de 3.500 € son 40 horas en las que ya ha escrito a otras dos clínicas.
> He grabado un vídeo de 2 minutos con cómo lo resolvería. ¿Te lo envío?

**Email 2 (día 3) — asunto: `re: vuestro formulario`**
> {nombre}, un dato: con 80 leads al mes, pasar de responder en horas a responder en 1 minuto suele significar 8-12 primeras visitas más. ¿Te paso el vídeo?

**DM (día 5)**
> Hola {nombre}, te escribí por email sobre la respuesta a los leads de {clínica}. Te dejo aquí la demo: escríbele como si fueras paciente → {enlace /demo}

**Email de cierre (día 9) — asunto: `¿lo cierro?`**
> No quiero insistir. Si responder a los leads en menos de 1 minuto no es prioridad ahora, lo dejo aquí. Si lo es, responde "vídeo" y te lo mando.

## Volumen y métricas objetivo
| Actividad | Semana |
|---|---|
| Prospectos nuevos auditados | 75 |
| Mensajes enviados (email + DM) | 200-300 |
| Respuestas positivas | 6-12 (3-5 %) |
| Llamadas de diagnóstico | 4-6 |
| Cierres | 1-2 |

## Demo que vende sola
Crea `clientes/<prospecto>.json` con sus datos reales (15 minutos) y envía el enlace `/demo/<prospecto>`.
Ver su propia clínica respondiendo a las 23:00 cierra más que cualquier presentación.
