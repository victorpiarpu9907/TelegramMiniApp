"use strict";

(function () {

const API = window.TelegramAPI;
    const DEMO = window.APP_CONFIG?.DEMO_MODE === true;

    const $ = selector => document.querySelector(selector);

    let busy = false;

    const USERBOT_STATES = {

not_configured: {
            title: "Sin configurar",
            description: "Faltan las credenciales de la cuenta de pruebas.",
            label: "Sin configurar",
            type: "neutral"
        },

stopped: {
            title: "Userbot detenido",
            description: "La cuenta está configurada, pero no hay conexión activa.",
            label: "Detenido",
            type: "neutral"
        },

connecting: {
            title: "Conectando...",
            description: "Estableciendo conexión con Telegram.",
            label: "Conectando",
            type: "neutral"
        },

running: {
            title: "Userbot conectado",
            description: "La conexión con Telegram está activa.",
            label: "Conectado",
            type: "ready"
        },

reconnecting: {
            title: "Recuperando conexión",
            description: "Telethon está intentando recuperar la conexión.",
            label: "Reconectando",
            type: "neutral"
        },

offline: {
            title: "Conexión perdida",
            description: "El Userbot ya no tiene una conexión activa.",
            label: "Desconectado",
            type: "error"
        },

error: {
            title: "Error de conexión",
            description: "Se ha producido un error. Revisa la configuración.",
            label: "Error",
            type: "error"
        }
    };

    const COLLECTOR_STATES = {

not_configured: ["Pendiente", "Todavía no se ha iniciado."],
        waiting_for_channel: ["Esperando canal", "Configura el canal principal."],
        running: ["Recolector activo", "Consultando nuevos movimientos."],
        paused: ["Recolector pausado", "El seguimiento está temporalmente detenido."],
        stopped: ["Detenido", "El recolector no está ejecutándose."],
        offline: ["Desconectado", "El Userbot perdió la conexión."],
        error: ["Error", "Revisa los registros del sistema."]
    };

    function setText(selector, value) {

        const element = $(selector);

if (element) {
            element.textContent = value;
        }
    }

    function setNotice(title, message, type = "info") {

        const notice = $("#userbotNotice");

        if (!notice) return;

notice.className = userbot-notice $DIL0;

const strong = notice.querySelector("strong");
        const paragraph = notice.querySelector("p");

if (strong) strong.textContent = title;
        if (paragraph) paragraph.textContent = message;
    }

    function renderStatus(data) {

const state = USERBOT_STATES[data.status] ||
            USERBOT_STATES.not_configured;

setText("#userbotStatusTitle", state.title);
        setText("#userbotStatusDescription", state.description);

        const badge = $("#userbotStatusBadge");

        if (badge) {

            badge.replaceChildren();

const dot = document.createElement("span");
dot.className = status-dot $DIL0;

const label = document.createElement("span");
            label.textContent = state.label;

badge.append(dot, label);
badge.className = userbot-status-badge $DIL0;
}

        const account = data.account;

        if (account) {

const fullName = [
                account.first_name,
                account.last_name
            ].filter(Boolean).join(" ");

setText(
                "#userbotAccountName",
                fullName || "Cuenta conectada"
            );

setText(
"#userbotAccountUsername",
account.username
? @$DIL0
: "Sin nombre de usuario"
);

setText(
                "#userbotAccountId",
                String(account.id)
            );

setText(
                "#userbotAccountAvatar",
                (account.first_name || "T").charAt(0).toUpperCase()
            );

        } else {

setText("#userbotAccountName", "Sin conexión");
            setText("#userbotAccountUsername", "Esperando autenticación");
            setText("#userbotAccountId", "—");
            setText("#userbotAccountAvatar", "?");

        }

setText(
            "#userbotSessionStatus",
            !data.configured
                ? "No configurada"
                : data.connected
                    ? "Autorizada"
                    : "Configurada"
        );

const collector = data.event_collector?.status ||
            "not_configured";

const collectorState = COLLECTOR_STATES[collector] ||
            ["Estado desconocido", "No se pudo determinar el estado."];

setText("#collectorStatusTitle", collectorState[0]);
        setText("#collectorStatusDescription", collectorState[1]);

setText(
            "#collectorHistoryStatus",
            collector === "running"
                ? "Seguimiento activo"
                : "Pendiente"
        );

        const heartbeat = data.last_heartbeat_at;

setText(
            "#userbotHeartbeat",
            heartbeat
                ? new Date(heartbeat).toLocaleString("es")
                : "Sin registros"
        );

const startButton = $("#userbotStartButton");
        const stopButton = $("#userbotStopButton");

        if (startButton) {

startButton.disabled = (
                DEMO ||
                busy ||
                !data.configured ||
                data.connected ||
                data.status === "connecting" ||
                data.status === "reconnecting"
            );

        }

        if (stopButton) {

stopButton.disabled = (
                DEMO ||
                busy ||
                !data.connected
            );

        }

        if (DEMO) {

setNotice(
                "Vista previa local",
                "Las operaciones están deshabilitadas. La conexión real se habilitará desde Telegram.",
                "info"
            );

        } else if (!data.configured) {

setNotice(
                "Configuración pendiente",
                "Primero debemos configurar API_ID, API_HASH y SESSION en el servidor.",
                "warning"
            );

        } else if (data.status === "running") {

setNotice(
                "Conexión activa",
                "El Userbot está conectado. El recolector funciona de manera independiente de las automatizaciones de mensajes.",
                "success"
            );

        } else {

setNotice(
                "Cuenta preparada",
                "La cuenta está configurada. Puedes iniciar el Userbot cuando estés listo.",
                "info"
            );

        }

    }

    function setBusy(value) {

        busy = value;

const startButton = $("#userbotStartButton");
        const stopButton = $("#userbotStopButton");
        const refreshButton = $("#userbotRefreshButton");

if (startButton) startButton.disabled = value || DEMO;
        if (stopButton) stopButton.disabled = value || DEMO;
        if (refreshButton) refreshButton.disabled = value;

    }

    async function refresh() {

        if (DEMO) {

renderStatus({
                status: "not_configured",
                configured: false,
                connected: false,
                account: null,
                last_heartbeat_at: null,
                event_collector: {
                    status: "not_configured"
                }
            });

            return;

        }

        try {

            const data = await API.userbotStatus();

            renderStatus(data);

            return data;

        } catch (error) {

setNotice(
                "No se pudo consultar el estado",
                error.message,
                "error"
            );

            throw error;

        }

    }

    async function start() {

        if (DEMO || busy) return;

        setBusy(true);

        try {

            const result = await API.startUserbot();

            renderStatus(result);

setNotice(
                "Solicitud completada",
                "El servidor respondió a la solicitud de conexión.",
                "success"
            );

        } catch (error) {

setNotice(
                "No se pudo iniciar",
                error.message,
                "error"
            );

        } finally {

            setBusy(false);

try {
                await refresh();
            } catch (_) {
                // El aviso de error ya fue mostrado.
            }

        }

    }

    async function stop() {

        if (DEMO || busy) return;

        setBusy(true);

        try {

            const result = await API.stopUserbot();

            renderStatus(result);

setNotice(
                "Userbot detenido",
                "La conexión se cerró de forma ordenada.",
                "info"
            );

        } catch (error) {

setNotice(
                "No se pudo detener",
                error.message,
                "error"
            );

        } finally {

            setBusy(false);

try {
                await refresh();
            } catch (_) {
                // El aviso de error ya fue mostrado.
            }

        }

    }

$("#userbotStartButton")?.addEventListener(
        "click",
        start
    );

$("#userbotStopButton")?.addEventListener(
        "click",
        stop
    );

$("#userbotRefreshButton")?.addEventListener(
        "click",
        async () => {

            try {

                await refresh();

if (!DEMO) {
                    setNotice(
                        "Estado actualizado",
                        "Se ha consultado nuevamente el estado del servidor.",
                        "success"
                    );
                }

} catch (_) {
                // El error ya se muestra en pantalla.
            }

}
    );

window.UserbotPanel = Object.freeze({
        refresh
    });

})();
