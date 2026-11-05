(() => {
  "use strict";

  const overlay = document.getElementById("mtejaModalOverlay");
  const byId = (id) => document.getElementById(id);

  function openBusinessDetails(row) {
    if (!row || !overlay) return;
    const values = {
      modalJinaDuka: row.dataset.businessName || "TradeCore Business",
      modalJinaMmiliki: row.dataset.ownerName || "-",
      modalEmail: row.dataset.ownerEmail || "-",
      modalSimu: row.dataset.businessPhone || "-",
      modalEneo: row.dataset.businessArea || "-",
      modalAina: row.dataset.businessType || "-",
      modalTin: row.dataset.businessTin || "-",
      modalTarehe: row.dataset.businessJoined || "-",
    };

    Object.entries(values).forEach(([id, value]) => {
      const element = byId(id);
      if (element) element.textContent = value;
    });

    const callButton = byId("modalPigaSimu");
    const phone = String(row.dataset.businessPhone || "").trim();
    const safePhone = phone.replace(/[^0-9+*#]/g, "");
    if (callButton) {
      if (phone && phone !== "-" && safePhone) {
        callButton.href = `tel:${safePhone}`;
        callButton.style.display = "flex";
      } else {
        callButton.removeAttribute("href");
        callButton.style.display = "none";
      }
    }

    overlay.classList.add("active");
  }

  function closeBusinessDetails() {
    overlay?.classList.remove("active");
  }

  document.addEventListener("click", (event) => {
    const refresh = event.target.closest("[data-control-room-action='refresh']");
    if (refresh) {
      window.location.reload();
      return;
    }

    const close = event.target.closest("[data-control-room-close]");
    if (close) {
      closeBusinessDetails();
      return;
    }

    if (overlay && event.target === overlay) {
      closeBusinessDetails();
      return;
    }

    const row = event.target.closest("[data-control-room-business]");
    if (row) openBusinessDetails(row);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeBusinessDetails();
      return;
    }

    if (event.key !== "Enter" && event.key !== " ") return;
    const row = event.target.closest?.("[data-control-room-business]");
    if (row) {
      event.preventDefault();
      openBusinessDetails(row);
    }
  });
})();
