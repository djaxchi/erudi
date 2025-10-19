// content_script.js
// Inject a small launcher and an iframe pointing to extension's widget.html
(function() {
  const IFRAME_ID = "erudit-widget-iframe-v1";
  const LAUNCHER_ID = "erudit-widget-launcher-v1";

  // Prevent double injection
  if (document.getElementById(IFRAME_ID) || document.getElementById(LAUNCHER_ID)) return;

  // Create launcher button (small round icon bottom-right)
  const launcher = document.createElement("button");
  launcher.id = LAUNCHER_ID;
  Object.assign(launcher.style, {
    position: "fixed",
    right: "18px",
    bottom: "18px",
    width: "56px",
    height: "56px",
    borderRadius: "50%",
    zIndex: 2147483646,
    border: "none",
    background: "linear-gradient(180deg,#25C08A,#1EAB78)",
    boxShadow: "0 6px 18px rgba(5,80,60,0.25)",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "0",
  });
  launcher.title = "Open Erudit Chat";
  const img = document.createElement("img");
  img.src = chrome.runtime.getURL("icons/icon-128.png");
  img.style.width = "26px";
  img.style.height = "26px";
  img.style.filter = "brightness(0) invert(1)";
  launcher.appendChild(img);
  document.documentElement.appendChild(launcher);

  // Create iframe that loads widget.html from extension
  const iframe = document.createElement("iframe");
  iframe.id = IFRAME_ID;
  iframe.src = chrome.runtime.getURL("widget.html");
  Object.assign(iframe.style, {
    position: "fixed",
    top: "6vh",
    right: "2.5vw",
    width: "16.6667vw", // 1/6th of width
    height: "25vh",     // 1/4 of height (approx)
    minWidth: "420px",
    minHeight: "360px",
    border: "none",
    borderRadius: "26px",
    zIndex: 2147483647,
    boxShadow: "0 8px 30px -4px rgba(0,0,0,0.45), 0 2px 6px -1px rgba(0,0,0,0.4)",
    overflow: "hidden",
  });

  // Start hidden? visible by default; user can close via widget UI
  document.documentElement.appendChild(iframe);

  // Toggle visibility through launcher
  launcher.addEventListener("click", () => {
    const isHidden = iframe.style.display === "none";
    iframe.style.display = isHidden ? "block" : "block"; // always show when clicking launcher
    // send a message to widget to focus (optional)
    iframe.contentWindow && iframe.contentWindow.postMessage({ type: "widget.open" }, "*");
  });

  // Listen for messages from iframe to allow closing from inside widget
  window.addEventListener("message", (ev) => {
    if (!ev.data || typeof ev.data !== "object") return;
    const msg = ev.data;
    if (msg.type === "widget.close") {
      iframe.style.display = "none";
    } else if (msg.type === "widget.minimize") {
      iframe.style.display = "none";
    }
  }, false);

  // Clean-up on unload (optional)
  window.addEventListener("beforeunload", () => {
    try {
      launcher.remove();
      iframe.remove();
    } catch(e) {}
  });
})();
