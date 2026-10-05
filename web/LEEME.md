# Web de Atiendia

Web estática (sin servidor) optimizada para Google. Coste: **0 € de alojamiento** (Netlify, plan gratuito)
+ **~10 €/año** por el dominio `atiendia.es`.

## 1. Rellena tus datos (10 min)
Busca y sustituye en todos los archivos:
- `[Tu nombre]`, `[Tu nombre y apellidos]`, `[tu NIF]`, `[tu dirección]`, `[fecha]`
- `hola@atiendia.es` → tu email de contacto (cuando tengas el dominio, crea ese buzón, ver paso 4)
- `https://g.page/r/TU-ENLACE-DE-GOOGLE/review` → tu enlace de reseñas de Google (paso 5)
- Tu foto: copia `foto.jpg` a esta carpeta y cambia la letra del bloque `.foto` en `index.html` por `<img src="foto.jpg" alt="[Tu nombre]">`

## 2. Publicar gratis en Netlify (15 min)
1. Crea una cuenta en https://app.netlify.com (puedes entrar con GitHub).
2. **Add new site → Import an existing project → GitHub** → elige el repositorio
   `no-se-que-poner-aun`, rama `claude/ai-agency-complete-n5uxrt`, **Base directory: `web`**.
   (Alternativa sin GitHub: *Deploy manually* y arrastra la carpeta `web`.)
3. Te dará una dirección tipo `atiendia.netlify.app`. Ya está en internet.

## 3. Recibir las solicitudes en tu email
1. En Netlify: **Site configuration → Forms → Enable form detection** y vuelve a desplegar.
2. **Forms → Form notifications → Add notification → Email notification** → tu email.
3. Haz una prueba rellenando el formulario. Llega a tu email y queda guardada en Netlify
   (plan gratuito: 100 solicitudes/mes).

## 4. Dominio propio (~10 €/año)
1. Compra `atiendia.es` en un registrador (DonDominio, Dinahosting, Namecheap…). Comprueba antes que está libre.
2. En Netlify: **Domain management → Add domain** → `atiendia.es` y sigue las instrucciones de DNS.
   El certificado HTTPS es gratis y automático.
3. Email `hola@atiendia.es`: muchos registradores incluyen un buzón o redirección gratis a tu Gmail.

## 5. Aparecer en Google
1. **Google Search Console** (gratis): añade `https://atiendia.es`, verifica y envía `sitemap.xml`.
2. **Perfil de Empresa de Google** (gratis, https://business.google.com): crea "Atiendia" como empresa de
   servicios (puedes ocultar tu dirección y poner "zona de servicio: España"). Desde ahí copia tu
   **enlace para pedir reseñas** y ponlo en la web.
3. Pide reseña a cada negocio con el que trabajes (los de prueba incluidos) cuando vean resultados.

## 6. Reseñas en la web
Cuando tengas reseñas **reales** en Google, cópialas al array `RESENAS` al final de `index.html`:
```js
var RESENAS = [
  { autor: "Nombre y negocio", estrellas: 5, texto: "Texto literal de la reseña", fecha: "noviembre 2026" }
];
```
Mientras esté vacío, la web muestra un mensaje de lanzamiento. No publiques reseñas inventadas:
es engañoso para los clientes, Google suspende perfiles por ello y en España puede sancionarse como
publicidad engañosa.
