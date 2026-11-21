"use strict";

(function () {

const API = window.TelegramAPI;
    const DEMO = window.APP_CONFIG?.DEMO_MODE === true;

    const list = document.getElementById("automationsList");

let items = [];
    let busyKeys = new Set();

const DEMO_ITEMS = [
        {
            key: "welcome_messages",
            name: "Mensajes de bienvenida",
            description: "Gestiona los mensajes privados enviados a los nuevos miembros del canal.",
            enabled: false
        },
        {
            key: "departure_messages",
            name: "Mensajes de despedida",
            description: "Gestiona los mensajes privados enviados a los miembros que abandonan el canal.",
            enabled: false
        },
        {
            key: "daily_summary",
            name: "Resumen diario",
            description: "Prepara un informe diario con las entradas, salidas y actividad del canal.",
            enabled: false
        }
    ];

function $(selector) {
        return document.querySelector(selector);
    }

    function showNotice(title, message, type = "info") {

        const notice = $("#automationNotice");

        if (!notice) return;

notice.className = automation-notice $DIL0;

notice.querySelector("strong").textContent = title;
        notice.querySelector("p").textContent = message;
    }

    function updateOverview() {

const active = items.filter(item => item.enabled).length;
        const paused = items.length - active;

$("#automationTotal").textContent = items.length;
        $("#automationActive").textContent = active;
        $("#automationPaused").textContent = paused;
    }

    function createSwitch(item) {

        const button = document.createElement("button");

button.type = "button";
        button.className = "automation-switch";

if (item.enabled) {
            button.classList.add("enabled");
        }

button.setAttribute("role", "switch");
button.setAttribute("aria-checked", String(item.enabled));
button.setAttribute(
"aria-label",
$DIL0 $DIL1
);

        button.dataset.automationKey = item.key;

const knob = document.createElement("span");
        knob.className = "automation-switch-knob";

        button.appendChild(knob);

        button.disabled = DEMO || busyKeys.has(item.key);

return button;
    }

    function createCard(item) {

const card = document.createElement("article");
        card.className = "automation-card";

const header = document.createElement("div");
        header.className = "automation-card-header";

const icon = document.createElement("div");
icon.className = automation-card-icon $DIL0;

icon.textContent = (
            item.key === "welcome_messages" ? "↗" :
            item.key === "departure_messages" ? "↙" :
            "◷"
        );

const copy = document.createElement("div");
        copy.className = "automation-card-copy";

const title = document.createElement("h3");
        title.textContent = item.name;

const description = document.createElement("p");
        description.textContent = item.description;

        copy.append(title, description);

        header.append(icon, copy);

const divider = document.createElement("div");
        divider.className = "automation-card-divider";

const footer = document.createElement("div");
        footer.className = "automation-card-footer";

const state = document.createElement("div");
        state.className = "automation-state";

const stateDot = document.createElement("span");
stateDot.className = automation-state-dot $DIL0;

        const stateText = document.createElement("span");

stateText.textContent = DEMO
            ? "Vista previa"
            : item.enabled
                ? "Automatización activa"
                : "Automatización pausada";

        state.append(stateDot, stateText);

const controls = document.createElement("div");
        controls.className = "automation-controls";

const switchLabel = document.createElement("span");
        switchLabel.className = "automation-switch-label";

switchLabel.textContent = item.enabled
            ? "Activada"
            : "Pausada";

controls.append(
            switchLabel,
            createSwitch(item)
        );

        footer.append(state, controls);

card.append(
            header,
            divider,
            footer
        );

return card;
    }

    function render() {

        list.replaceChildren();

items.forEach(item => {
            list.appendChild(createCard(item));
        });

        updateOverview();

    }

    async function refresh() {

        if (DEMO) {

            items = DEMO_ITEMS.map(item => ({ ...item }));

            render();

showNotice(
                "Vista previa local",
                "Los interruptores están desactivados. Los cambios reales se guardarán en SQLite cuando conectemos la Mini App.",
                "info"
            );

return items;
        }

        try {

            const result = await API.automations();

            items = result.items || [];

            render();

showNotice(
                "Configuración actualizada",
                "Los estados se han consultado directamente desde el servidor.",
                "success"
            );

            return items;

        } catch (error) {

showNotice(
                "Error al consultar automatizaciones",
                error.message,
                "error"
            );

            throw error;

        }

    }

    async function toggle(key) {

        if (DEMO || busyKeys.has(key)) return;

        const item = items.find(entry => entry.key === key);

        if (!item) return;

        const previousValue = item.enabled;

busyKeys.add(key);
        render();

        try {

const result = await API.updateAutomation(
                key,
                !previousValue
            );

            item.enabled = result.enabled;

showNotice(
"Cambio guardado",
result.enabled
? $DIL0 ha sido activada.
: $DIL1 ha sido pausada.,
"success"
);

        } catch (error) {

showNotice(
                "No se pudo actualizar",
                error.message,
                "error"
            );

        } finally {

busyKeys.delete(key);
            render();

        }

    }

    list.addEventListener("click", event => {

const button = event.target.closest(
            "[data-automation-key]"
        );

        if (!button) return;

        toggle(button.dataset.automationKey);

    });

$("#automationRefreshButton")?.addEventListener(
        "click",
        async () => {

if (DEMO) {
                await refresh();
                return;
            }

            try {

                await refresh();

} catch (_) {
                // El aviso de error ya está visible.
            }

}
    );

window.AutomationsPanel = Object.freeze({
        refresh
    });

})();


// Render inicial de la vista previa local
if (DEMO) {
    refresh();
}
