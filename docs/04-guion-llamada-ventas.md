# 4. Guion de la llamada de diagnóstico (30 min)

**Objetivo:** que el cliente cuantifique su pérdida y pida la solución. Tú preguntas el 70 % del tiempo.

## 1. Marco (2 min)
"Gracias por el tiempo. La idea es entender cómo os llegan los pacientes y dónde se pierden. Si veo que puedo ayudar te cuento cómo; si no, te lo digo igual. ¿Te parece?"

## 2. Situación (8 min)
- ¿Cuántas consultas/leads entran al mes? ¿Por qué canales?
- ¿Quién responde y en qué horario? ¿Qué pasa con lo que entra por la noche o en fin de semana?
- ¿Qué tratamiento os deja más margen? ¿Ticket medio?
- ¿Cuántos presupuestos se quedan sin aceptar? ¿Hacéis seguimiento?
- ¿Cuántos pacientes no se presentan a la cita?
- ¿Cuántos pacientes antiguos tenéis en la base de datos que no han vuelto en 12 meses?

## 3. Cuantificar (8 min)
Calcula en vivo con `python cli.py roi --leads X --ticket Y` o `POST /api/roi`:
"Con {X} leads y un ticket de {Y} €, responder en 1 minuto en lugar de en horas supone unos {ventas_extra} pacientes más al mes, unos {ingreso_extra} € al mes. ¿Te cuadra?"
Deja que el cliente corrija la cifra: si la corrige él, se la cree.

## 4. Solución (7 min)
Enseña la demo con SU negocio (`/demo/<prospecto>`). Escribe tú como paciente delante de él.
Explica en 3 frases: responde en segundos, califica, reserva; seguimiento automático; panel con resultados.

## 5. Cierre (5 min)
"Lo recomendable para vuestro volumen es el plan Crecimiento: 1.997 € de puesta en marcha y 997 €/mes, con garantía de 60 días. Si lo arrancamos esta semana, en 14 días está funcionando. ¿Lo ponemos en marcha?"

### Objeciones
| Objeción | Respuesta |
|---|---|
| "Es caro" | "Comparado con ¿qué? Hemos calculado {ingreso_extra} €/mes perdidos. La cuota es {cuota}. ¿Qué parte del cálculo no te convence?" |
| "Ya tenemos recepcionista" | "Perfecto, esto no la sustituye: cubre noches, fines de semana y picos, y le deja los leads calificados." |
| "Los pacientes quieren hablar con personas" | "Por eso escala a tu equipo en cuanto alguien lo pide o hay algo delicado. Pruébalo tú ahora en la demo." |
| "Me lo tengo que pensar" | "Claro. ¿Qué tendría que ser verdad para que fuera un sí?" — o propone la reactivación a éxito, sin riesgo. |
| "¿Y si la IA dice algo incorrecto?" | "Solo responde con la ficha que validas tú; no diagnostica ni promete resultados; todo queda registrado en el panel." |
