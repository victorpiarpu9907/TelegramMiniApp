"use strict";

(function () {
    const API = window.TelegramAPI;
    const DEMO = window.APP_CONFIG && window.APP_CONFIG.DEMO_MODE === true;
    const $ = (selector) => document.querySelector(selector);

    let channelData = null;
    let busy = false;

    function setText(selector, value) {
        const element = $(selector);
        if (element) element.textContent = String(value);
    }

    function showNotice(title, message, type = "info") {
        const notice = $("#channelNotice");
        if (!notice) {
            console.error("Falta #channelNotice en index.html");
            return;
        }
        notice.className = "channel-notice " + type;
        const heading = notice.querySelector("strong");
        const paragraph = notice.querySelector("p");
        if (heading) heading.textContent = title;
        if (paragraph) paragraph.textContent = message;
    }

    function formatDate(value) {
        if (!value) return "Sin registros";
        const date = new Date(value);
        return Number.isNaN(date.getTime())
            ? "Sin registros"
            : date.toLocaleString("es");
    }

    function render(data) {
        channelData = data;
        const channel = data.channel || {};
        const collector = data.collector || {};
        const history = data.history || {};
        const configured = Boolean(data.configured);
        const enabled = Boolean(channel.enabled);

        const idInput = $("#channelId");
        const titleInput = $("#channelTitle");
        const enabledInput = $("#channelEnabled");
        if (idInput) idInput.value = channel.telegram_channel_id == null ? "" : String(channel.telegram_channel_id);
        if (titleInput) titleInput.value = channel.title || "";
        if (enabledInput) enabledInput.checked = enabled;

        setText("#channelTrackingStatus", !configured
            ? "Sin configurar"
            : enabled ? "Seguimiento habilitado" : "Seguimiento pausado");

        setText("#channelTrackingDescription", !configured
            ? "Primero debes registrar un canal."
            : enabled
                ? "El recolector podrÃ¡ registrar movimientos cuando el Userbot estÃ© conectado."
                : "El registro de movimientos estÃ¡ temporalmente pausado.");

        const badge = $("#channelTrackingBadge");
        if (badge) {
            const dot = document.createElement("span");
            dot.className = "status-dot " + (configured && enabled ? "status-active" : "status-neutral");
            const label = document.createElement("span");
            label.textContent = !configured ? "Sin configurar" : enabled ? "Habilitado" : "Pausado";
            badge.replaceChildren(dot, label);
        }

        const trackingButton = $("#channelTrackingButton");
        if (trackingButton) {
            trackingButton.disabled = DEMO || busy || !configured;
            trackingButton.textContent = enabled ? "Pausar seguimiento" : "Activar seguimiento";
        }
        const saveButton = $("#channelSaveButton");
        if (saveButton) saveButton.disabled = busy;

        const validationPending = data.telegram_validation === "pending";
        setText("#channelValidationStatus", validationPending ? "Pendiente de validaciÃ³n" : "Sin configurar");
        setText("#channelValidationDescription", validationPending
            ? "El ID estÃ¡ guardado, pero aÃºn no se ha comprobado el acceso real."
            : "Registra un canal para comenzar.");

        const completed = Boolean(history.backfill_completed);
        setText("#channelHistoryStatus", completed
            ? "ImportaciÃ³n inicial completada"
            : configured ? "Pendiente de importaciÃ³n" : "Sin configurar");
        setText("#channelHistoryDescription", completed
            ? "La recuperaciÃ³n histÃ³rica inicial quedÃ³ registrada."
            : "Al conectar el Userbot se intentarÃ¡ recuperar la actividad disponible de las Ãºltimas 24 horas.");
        setText("#channelLastEvent", Number(history.last_event_id || 0).toLocaleString("es"));
        setText("#channelLastSync", formatDate(history.last_sync_at));
        setText("#channelCollectorStatus", collector.status || "Pendiente");

        if (DEMO) {
            showNotice("Vista previa local", "Puedes completar el formulario, pero no se guardarÃ¡ nada en el servidor.");
        } else if (!configured) {
            showNotice("Configura tu canal", "Introduce un ID numÃ©rico negativo vÃ¡lido.", "warning");
        } else if (validationPending) {
            showNotice("Canal pendiente de validaciÃ³n", "La comprobaciÃ³n de Telegram se harÃ¡ cuando se conecte el Userbot.", "warning");
        } else {
            showNotice("ConfiguraciÃ³n consultada", "Se recuperaron los datos guardados en el servidor.", "success");
        }
    }

    async function refresh() {
        if (DEMO) {
            const demoData = {
                configured: false,
                channel: { telegram_channel_id: null, title: null, enabled: false },
                collector: { status: "not_configured" },
                history: { backfill_completed: false, last_event_id: 0, last_sync_at: null },
                telegram_validation: "not_configured"
            };
            render(demoData);
            return demoData;
        }
        try {
            if (!API) throw new Error("No se cargÃ³ el cliente de la API.");
            const data = await API.channel();
            render(data);
            return data;
        } catch (error) {
            showNotice("Error al consultar el canal", error.message, "error");
            throw error;
        }
    }

    async function save(event) {
        event.preventDefault(); // Nunca enviar el formulario HTML de forma tradicional.
        if (busy) return;

        const idInput = $("#channelId");
        const titleInput = $("#channelTitle");
        const enabledInput = $("#channelEnabled");
        if (!idInput || !titleInput || !enabledInput) {
            showNotice("Formulario incompleto", "Faltan elementos de la pantalla del canal.", "error");
            return;
        }

        const rawId = idInput.value.trim();
        const id = Number(rawId);
        if (!/^-\d+$/.test(rawId) || !Number.isSafeInteger(id)) {
            showNotice("ID invÃ¡lido", "Introduce un nÃºmero entero negativo de Telegram.", "error");
            return;
        }

        const title = titleInput.value.trim();
        if (title.length > 255) {
            showNotice("Nombre demasiado largo", "El nombre no puede superar 255 caracteres.", "error");
            return;
        }

        if (DEMO) {
            showNotice(
                "Modo DEMO: sin cambios guardados",
                "El canal " + rawId + " no se ha enviado al servidor. El formulario solo es una vista previa."
            );
            return;
        }

        busy = true;
        const saveButton = $("#channelSaveButton");
        const trackingButton = $("#channelTrackingButton");
        if (saveButton) saveButton.disabled = true;
        if (trackingButton) trackingButton.disabled = true;
        try {
            if (!API) throw new Error("No se cargÃ³ el cliente de la API.");
            await API.updateChannel({
                telegram_channel_id: id,
                title: title || null,
                enabled: enabledInput.checked
            });
            await refresh();
            showNotice("ConfiguraciÃ³n guardada", "El canal quedÃ³ guardado. AÃºn falta validarlo con Telegram.", "success");
        } catch (error) {
            showNotice("No se pudo guardar", error.message, "error");
        } finally {
            busy = false;
            if (saveButton) saveButton.disabled = false;
            if (trackingButton) trackingButton.disabled = DEMO || !channelData || !channelData.configured;
        }
    }

    async function toggleTracking() {
        if (DEMO || busy || !channelData || !channelData.configured) return;
        const enabled = !Boolean(channelData.channel.enabled);
        busy = true;
        const trackingButton = $("#channelTrackingButton");
        if (trackingButton) trackingButton.disabled = true;
        try {
            await API.updateTracking(enabled);
            await refresh();
            showNotice("Seguimiento actualizado", enabled ? "Seguimiento habilitado." : "Seguimiento pausado.", "success");
        } catch (error) {
            showNotice("No se pudo cambiar el seguimiento", error.message, "error");
        } finally {
            busy = false;
            if (trackingButton) trackingButton.disabled = DEMO || !channelData || !channelData.configured;
        }
    }

    const form = $("#channelForm");
    if (!form) {
        console.error("No se encontrÃ³ #channelForm: verifica index.html");
        return;
    }
    form.addEventListener("submit", save);
    $("#channelTrackingButton")?.addEventListener("click", toggleTracking);
    $("#channelRefreshButton")?.addEventListener("click", function () {
        refresh().catch(function () { /* El error ya se mostrÃ³. */ });
    });

    window.ChannelPanel = Object.freeze({ refresh: refresh });
    console.info("ChannelPanel cargado correctamente.");
})();