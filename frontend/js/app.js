"use strict";

const toast = document.getElementById("toast");
const sidebar = document.getElementById("sidebar");

let toastTimer = null;
let currentView = "dashboard";


const PAGE_NAMES = {
    dashboard: "Dashboard",
    userbot: "Control del Userbot",
    automations: "Automatizaciones",
    channel: "Canal principal",
    statistics: "Estadísticas"
};


function showToast(message) {

    toast.textContent = message;
    toast.classList.add("show");

    clearTimeout(toastTimer);

    toastTimer = setTimeout(() => {
        toast.classList.remove("show");
    }, 3200);
}


function updateDate() {

    const element = document.getElementById("currentDate");

    if (!element) return;

    element.textContent = new Intl.DateTimeFormat("es", {
        weekday: "short",
        day: "numeric",
        month: "short",
        year: "numeric"
    }).format(new Date());
}


function navigateTo(view) {

    const target = document.getElementById(`${view}View`);

    if (!target) {

        showToast(
            "Esta sección se habilitará en una próxima fase."
        );

        return;
    }

    currentView = view;

    document.querySelectorAll(".view-page").forEach(page => {

        page.classList.toggle(
            "active",
            page.dataset.page === view
        );

    });

    document.querySelectorAll(".nav-item").forEach(item => {

        item.classList.toggle(
            "active",
            item.dataset.view === view
        );

    });

    const breadcrumb = document.querySelector(
        ".breadcrumb strong"
    );

    if (breadcrumb) {
        breadcrumb.textContent = PAGE_NAMES[view] || view;
    }

    sidebar.classList.remove("open");

    if (view === "userbot") {
        window.UserbotPanel?.refresh().catch(() => {});
    }

    if (view === "automations") {
        window.AutomationsPanel?.refresh().catch(() => {});
    }

    if (view === "channel") {
        window.ChannelPanel?.refresh().catch(() => {});
    }

    if (view === "statistics") {
        window.StatisticsPanel?.refresh().catch(() => {});
    }

    if (
        view === "dashboard" &&
        !window.APP_CONFIG.DEMO_MODE
    ) {

        window.Dashboard.refresh().catch(error => {
            showToast(error.message);
        });

    }

}


document.querySelectorAll(".nav-item").forEach(item => {

    item.addEventListener("click", () => {
        navigateTo(item.dataset.view);
    });

});


document.querySelectorAll("[data-action]").forEach(button => {

    button.addEventListener("click", () => {

        const action = button.dataset.action;

        const supportedViews = [
            "userbot",
            "automations",
            "channel"
        ];

        if (supportedViews.includes(action)) {
            navigateTo(action);
            return;
        }

        const messages = {
            creator: "El creador de canales se desarrollará próximamente.",
            contacts: "La gestión de contactos se desarrollará próximamente.",
            activity: "El historial se desarrollará próximamente."
        };

        showToast(
            messages[action] || "Funcionalidad en desarrollo."
        );

    });

});


document.getElementById("refreshButton").addEventListener(
    "click",
    async () => {

        try {

            if (currentView === "userbot") {

                await window.UserbotPanel.refresh();

            } else if (currentView === "automations") {

                await window.AutomationsPanel.refresh();

            } else if (currentView === "channel") {

                await window.ChannelPanel.refresh();

            } else if (currentView === "statistics") {
                await window.StatisticsPanel.refresh();
            } else if (window.APP_CONFIG.DEMO_MODE) {

                showToast(
                    "Estás en vista previa local. No hay datos reales que actualizar."
                );

                return;

            } else {

                await window.Dashboard.refresh();

            }

            showToast("Información actualizada.");

        } catch (error) {

            showToast(error.message);

        }

    }
);


document.getElementById("connectButton").addEventListener(
    "click",
    () => {
        navigateTo("userbot");
    }
);


document.getElementById("menuToggle").addEventListener(
    "click",
    () => {
        sidebar.classList.toggle("open");
    }
);


document.addEventListener("click", event => {

    const insideSidebar = sidebar.contains(event.target);
    const clickedMenu = event.target.closest("#menuToggle");

    if (
        window.innerWidth <= 850 &&
        !insideSidebar &&
        !clickedMenu
    ) {
        sidebar.classList.remove("open");
    }

});



// CHANNEL_FORM_SUBMIT_GUARD
// Evita el envío HTML tradicional del formulario.

document.addEventListener("submit", function(event) {

    if (event.target.id !== "channelForm") {
        return;
    }

    event.preventDefault();

    // En modo DEMO solo mostramos una notificación.
    if (window.APP_CONFIG?.DEMO_MODE === true) {

        showToast(
            "Modo DEMO: la configuración no se ha guardado en el servidor."
        );

        return;
    }

    // Evitar una falsa confirmación si falta el controlador.
    if (!window.ChannelPanel) {

        showToast(
            "Error: no se ha cargado el controlador del canal."
        );

    }

}, true);
updateDate();


if (window.Telegram?.WebApp) {

    window.Telegram.WebApp.ready();
    window.Telegram.WebApp.expand();

}


if (!window.APP_CONFIG.DEMO_MODE) {

    const badge = document.querySelector(".environment-badge");

    badge.innerHTML = `
        <span class="environment-dot"></span>
        MINI APP TELEGRAM
    `;

    window.Dashboard.initialize().catch(error => {
        showToast(error.message);
    });

}


console.info(
    "Telegram Control Center | Navegación inicializada."
);
