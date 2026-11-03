// Apply the saved theme before first paint. With no saved choice the OS preference wins (CSS media query).
(function () {
  try {
    var saved = localStorage.getItem("sis-theme");
    if (saved === "light" || saved === "dark") document.documentElement.setAttribute("data-theme", saved);
  } catch (e) { /* storage blocked: fall back to the OS preference */ }
})();
