/*!
 * BotForge widget: embed with one tag:
 *   <script src="https://YOUR-API/widget.js" data-bot-id="bot_xxx" async></script>
 * Optional: data-position="left", data-open="true"
 * Renders inside a shadow root so host-page CSS can't leak in (or out).
 */
(function () {
  "use strict";
  var script = document.currentScript;
  if (!script || window.__botforgeLoaded) return;
  window.__botforgeLoaded = true;

  var BOT = script.getAttribute("data-bot-id");
  var API = new URL(script.src).origin;
  var LEFT = script.getAttribute("data-position") === "left";
  if (!BOT) { console.warn("[botforge] missing data-bot-id"); return; }

  // Fonts must be registered on the document, not inside the shadow root.
  if (!document.querySelector("link[data-botforge-font]")) {
    var l = document.createElement("link");
    l.rel = "stylesheet"; l.setAttribute("data-botforge-font", "");
    l.href = "https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap";
    document.head.appendChild(l);
  }

  var CSS = `
  :host { all: initial; }
  * { box-sizing: border-box; }
  .root { --paper:#F2EDDF; --paper2:#F8F4EA; --ink:#111; --ink2:#5E5B53; --line:rgba(17,17,17,.16);
    font-family: Manrope, ui-sans-serif, system-ui, sans-serif; color: var(--ink);
    position: fixed; bottom: 24px; ${LEFT ? "left" : "right"}: 24px; z-index: 2147483000; }
  .launcher { display:flex; align-items:center; gap:12px; height:56px; padding:0 10px 0 24px;
    border:0; border-radius:999px; background:var(--ink); color:var(--paper); cursor:pointer;
    font: 600 16px Manrope, system-ui, sans-serif; letter-spacing:-.01em;
    box-shadow: 0 12px 28px -12px rgba(0,0,0,.45); transition: transform .15s ease-out; }
  .launcher:hover { transform: translateY(-1px); }
  .launcher b { font-weight:800; }
  .arrow { width:34px; height:34px; border:1.5px solid var(--paper); border-radius:50%;
    display:grid; place-items:center; transition: transform .15s ease-out; }
  .launcher:hover .arrow { transform: rotate(45deg); }
  .panel { position:absolute; bottom:72px; ${LEFT ? "left" : "right"}:0; width:min(380px, calc(100vw - 32px));
    height:min(560px, calc(100vh - 120px)); display:none; flex-direction:column; overflow:hidden;
    background-color: var(--paper);
    background-image: radial-gradient(rgba(20,20,20,.22) 1px, transparent 1.2px); background-size: 28px 28px;
    border:1px solid var(--line); border-radius:6px; box-shadow: 0 1px 0 rgba(0,0,0,.04), 0 24px 48px -20px rgba(40,30,10,.45); }
  .panel.open { display:flex; animation: pop .25s ease-out; }
  @keyframes pop { from { opacity:0; transform: translateY(8px); } to { opacity:1; transform:none; } }
  header { display:flex; align-items:center; justify-content:space-between; padding:16px 18px;
    background: var(--paper2); border-bottom:1px solid var(--line); }
  .brand { font-weight:800; font-size:17px; letter-spacing:-.02em; display:flex; gap:8px; align-items:center; text-transform: lowercase; }
  .close { border:0; background:none; font-size:22px; line-height:1; cursor:pointer; color:var(--ink); padding:4px 6px; }
  .msgs { flex:1; overflow-y:auto; padding:18px; display:flex; flex-direction:column; gap:10px; }
  .msg { max-width:85%; padding:10px 14px; font-size:14.5px; line-height:1.5; white-space:pre-wrap; word-wrap:break-word; }
  .bot { align-self:flex-start; background:var(--paper2); border:1px solid var(--line); border-radius:18px 18px 18px 4px; }
  .user { align-self:flex-end; background:var(--ink); color:var(--paper); border-radius:18px 18px 4px 18px; }
  .err { align-self:center; font-size:13px; color:#A33A2B; }
  .typing span { display:inline-block; width:6px; height:6px; margin:0 2px; border-radius:50%; background:var(--ink2); animation: b 1s infinite; }
  .typing span:nth-child(2){animation-delay:.15s} .typing span:nth-child(3){animation-delay:.3s}
  @keyframes b { 0%,80%,100%{transform:scale(.6);opacity:.5} 40%{transform:scale(1);opacity:1} }
  form { display:flex; gap:8px; padding:12px; background:var(--paper2); border-top:1px solid var(--line); }
  input { flex:1; height:44px; border:1px solid var(--line); border-radius:999px; padding:0 16px;
    background:var(--paper); font: 500 14.5px Manrope, system-ui, sans-serif; color:var(--ink); outline:none; }
  input:focus { border-color: var(--ink); } input:focus-visible { outline: none; }
  .send { width:44px; height:44px; border:0; border-radius:50%; background:var(--ink); color:var(--paper); cursor:pointer; display:grid; place-items:center; }
  .send:disabled { opacity:.4; cursor:default; }
  .foot { text-align:center; font-size:11px; color:var(--ink2); padding:0 0 8px; background:var(--paper2); }
  :focus-visible { outline:2px solid var(--ink); outline-offset:2px; }
  @media (prefers-reduced-motion: reduce) { * { animation:none !important; transition:none !important; } }`;

  var ARROW = '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M5 11L11 5M6 5h5v5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var STAR = '<svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 1l1.6 7.2L20 4l-4.2 6.4L23 12l-7.2 1.6L20 20l-6.4-4.2L12 23l-1.6-7.2L4 20l4.2-6.4L1 12l7.2-1.6L4 4l6.4 4.2z"/></svg>';

  var host = document.createElement("div");
  host.id = "botforge-widget";
  var shadow = host.attachShadow({ mode: "open" });
  shadow.innerHTML = '<style>' + CSS + '</style>' +
    '<div class="root">' +
      '<div class="panel" role="dialog" aria-label="chat">' +
        '<header><div class="brand">' + STAR + '<span class="name">assistant</span></div>' +
        '<button class="close" aria-label="close chat">×</button></header>' +
        '<div class="msgs" aria-live="polite"></div>' +
        '<form><input name="q" autocomplete="off" maxlength="1000" placeholder="ask a question…" aria-label="your question"/>' +
        '<button class="send" type="submit" aria-label="send">' + ARROW + '</button></form>' +
        '<div class="foot">powered by botforge</div>' +
      '</div>' +
      '<button class="launcher" aria-label="open chat"><span>say hi to <b class="lname">us</b></span><span class="arrow">' + ARROW + '</span></button>' +
    '</div>';
  document.body.appendChild(host);

  var $ = function (s) { return shadow.querySelector(s); };
  var panel = $(".panel"), msgs = $(".msgs"), form = $("form"), input = $("input"), send = $(".send");
  var history = [], busy = false, greeted = false;

  function add(cls, text) {
    var d = document.createElement("div");
    d.className = "msg " + cls; d.textContent = text || "";
    msgs.appendChild(d); msgs.scrollTop = msgs.scrollHeight; return d;
  }
  function toggle(open) {
    panel.classList.toggle("open", open);
    if (open) { input.focus(); if (!greeted) { greeted = true; add("bot", info.greeting); } }
  }

  var info = { name: "assistant", greeting: "hi! ask me anything." };
  fetch(API + "/public/bots/" + encodeURIComponent(BOT))
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (j) { info = j; $(".name").textContent = j.name; $(".lname").textContent = j.name.toLowerCase(); })
    .catch(function () { $(".lname").textContent = "us"; })
    .finally(function () { if (script.getAttribute("data-open") === "true") toggle(true); });

  $(".launcher").addEventListener("click", function () { toggle(!panel.classList.contains("open")); });
  $(".close").addEventListener("click", function () { toggle(false); });

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    var q = input.value.trim();
    if (!q || busy) return;
    busy = true; send.disabled = true; input.value = "";
    add("user", q);
    var bubble = add("bot typing", ""); bubble.innerHTML = "<span></span><span></span><span></span>";
    var answer = "";
    try {
      var res = await fetch(API + "/public/bots/" + encodeURIComponent(BOT) + "/chat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: q, history: history.slice(-10) }),
      });
      if (!res.ok) throw new Error(res.status === 403 ? "this site isn't allowed to use this bot." : "something went wrong (" + res.status + ").");
      var reader = res.body.getReader(), dec = new TextDecoder(), buf = "";
      for (;;) {
        var r = await reader.read(); if (r.done) break;
        buf += dec.decode(r.value, { stream: true });
        var frames = buf.split("\n\n"); buf = frames.pop();
        for (var i = 0; i < frames.length; i++) {
          var line = frames[i].replace(/^data: /, ""); if (!line) continue;
          var ev = JSON.parse(line);
          if (ev.type === "token") {
            if (!answer) { bubble.className = "msg bot"; bubble.textContent = ""; }
            answer += ev.text; bubble.textContent = answer; msgs.scrollTop = msgs.scrollHeight;
          } else if (ev.type === "error") { throw new Error("the assistant is unavailable right now."); }
        }
      }
      history.push({ role: "user", content: q }, { role: "assistant", content: answer });
    } catch (err) {
      bubble.remove(); add("err", err.message || "network error");
    } finally { busy = false; send.disabled = false; input.focus(); }
  });
})();
