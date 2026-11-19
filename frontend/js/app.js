"use strict";

const toast = document.getElementById("toast");
const sidebar = document.getElementById("sidebar");

let toastTimer = null;


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

    element.textContent = new Intl.DateTimeFormat("es", {
        weekday: "short",
        day: "numeric",
        month: "short",
        year: "numeric"
    }).format(new Date());
}


function navigateTo(view) {

    if (view !== "dashboard") {

        showToast(
            "Esta sección se habilitará en la siguiente fase."
        );

        return;
    }

    document.querySelectorAll(".nav-item").forEach(item => {

        item.classList.toggle(
            "active",
            item.dataset.view === view
        );

    });

    sidebar.classList.remove("open");
}


document.querySelectorAll(".nav-item").forEach(item => {

    item.addEventListener("click", () => {
        navigateTo(item.dataset.view);
    });

});


document.querySelectorAll("[data-action]").forEach(button => {

    button.addEventListener("click", () => {

        const action = button.dataset.action;

        const messages = {
            userbot: "El control del userbot se habilitará en la siguiente fase.",
            automations: "El panel de automatizaciones está en desarrollo.",
            channel: "La configuración del canal está preparada en el backend.",
            creator: "El creador de canales se desarrollará próximamente.",
            activity: "El historial se conectará con la base de datos."
        };

        showToast(
            messages[action] || "Funcionalidad en desarrollo."
        );

    });

});


document.getElementById("refreshButton").addEventListener(
    "click",
    async () => {

        if (window.APP_CONFIG.DEMO_MODE) {

            showToast(
                "Estás en vista previa. Los datos reales se activarán al publicar la Mini App."
            );

            return;
        }

        try {

            await window.Dashboard.refresh();

            showToast("Dashboard actualizado correctamente.");

        } catch (error) {

            showToast(error.message);

        }

    }
);


document.getElementById("connectButton").addEventListener(
    "click",
    () => {

        showToast(
            "El control real del userbot se habilitará después de configurar la cuenta de pruebas."
        );

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


updateDate();

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
    "Telegram Control Center | Frontend inicializado."
);
