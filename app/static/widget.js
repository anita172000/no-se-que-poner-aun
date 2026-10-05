/* Widget de chat embebible.
   Uso en la web del cliente:
   <script src="https://TU-DOMINIO/static/widget.js" data-cliente="clinica-lumiere" data-color="#0f766e"></script> */
(function () {
  var s = document.currentScript;
  var cliente = s.getAttribute("data-cliente");
  var color = s.getAttribute("data-color") || "#0f766e";
  var titulo = s.getAttribute("data-titulo") || "¿Te ayudamos?";
  var base = s.src.replace(/\/static\/widget\.js.*$/, "");
  var clave = "agencia_conv_" + cliente;
  var conv = null;
  try { conv = localStorage.getItem(clave); } catch (e) {}

  var css = document.createElement("style");
  css.textContent =
    ".aw-btn{position:fixed;right:20px;bottom:20px;width:60px;height:60px;border-radius:50%;border:0;cursor:pointer;color:#fff;font-size:26px;box-shadow:0 6px 20px rgba(0,0,0,.25);z-index:99999}" +
    ".aw-box{position:fixed;right:20px;bottom:92px;width:min(360px,calc(100vw - 32px));height:min(520px,calc(100vh - 120px));background:#fff;color:#111;border-radius:16px;box-shadow:0 10px 40px rgba(0,0,0,.25);display:none;flex-direction:column;overflow:hidden;z-index:99999;font:15px/1.4 system-ui,sans-serif}" +
    ".aw-head{padding:14px 16px;color:#fff;font-weight:600}.aw-log{flex:1;overflow:auto;padding:12px;display:flex;flex-direction:column;gap:8px;background:#f6f7f9}" +
    ".aw-m{max-width:80%;padding:8px 12px;border-radius:14px;white-space:pre-wrap}.aw-u{align-self:flex-end;color:#fff}.aw-a{align-self:flex-start;background:#fff;border:1px solid #e5e7eb}" +
    ".aw-f{display:flex;border-top:1px solid #e5e7eb}.aw-f input{flex:1;border:0;padding:12px;font:inherit;outline:none}.aw-f button{border:0;background:none;padding:0 14px;font-weight:600;cursor:pointer}";
  document.head.appendChild(css);

  var btn = document.createElement("button");
  btn.className = "aw-btn"; btn.style.background = color; btn.textContent = "💬"; btn.setAttribute("aria-label", "Abrir chat");
  var box = document.createElement("div");
  box.className = "aw-box";
  box.innerHTML = '<div class="aw-head"></div><div class="aw-log"></div><form class="aw-f"><input placeholder="Escribe tu mensaje…" aria-label="Mensaje"><button>Enviar</button></form>';
  box.querySelector(".aw-head").style.background = color;
  box.querySelector(".aw-head").textContent = titulo;
  box.querySelector(".aw-f button").style.color = color;
  document.body.appendChild(btn); document.body.appendChild(box);
  var log = box.querySelector(".aw-log"), form = box.querySelector("form"), input = form.querySelector("input");

  function add(texto, quien) {
    var d = document.createElement("div");
    d.className = "aw-m " + (quien === "u" ? "aw-u" : "aw-a");
    if (quien === "u") d.style.background = color;
    d.textContent = texto; log.appendChild(d); log.scrollTop = log.scrollHeight; return d;
  }
  btn.onclick = function () {
    var abierto = box.style.display === "flex";
    box.style.display = abierto ? "none" : "flex";
    if (!abierto && !log.children.length) add("¡Hola! 👋 ¿En qué te puedo ayudar?", "a");
    if (!abierto) input.focus();
  };
  form.onsubmit = function (ev) {
    ev.preventDefault();
    var t = input.value.trim(); if (!t) return;
    input.value = ""; add(t, "u");
    var esperando = add("…", "a");
    fetch(base + "/api/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cliente_id: cliente, mensaje: t, conversacion_id: conv, canal: "web" })
    }).then(function (r) { return r.json(); }).then(function (d) {
      conv = d.conversacion_id; try { localStorage.setItem(clave, conv); } catch (e) {}
      esperando.textContent = d.respuesta || "Perdona, ¿puedes repetirlo?";
    }).catch(function () { esperando.textContent = "Ups, no hay conexión. Inténtalo de nuevo."; });
  };
})();
