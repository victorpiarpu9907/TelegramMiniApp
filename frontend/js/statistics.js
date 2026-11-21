"use strict";

(function () {
    const API = window.TelegramAPI;
    const DEMO = window.APP_CONFIG?.DEMO_MODE === true;
    const $ = id => document.getElementById(id);
    const nf = new Intl.NumberFormat("es");
    let sequence = 0;

    const STATUS = {
        running: "Activo", paused: "Pausado", stopped: "Detenido",
        waiting_for_channel: "Esperando canal", reconnecting: "Reconectando",
        offline: "Desconectado", error: "Error", not_configured: "Sin configurar"
    };

    function text(id, value) {
        const element = $(id);
        if (element) element.textContent = value;
    }

    function number(value, signed = false) {
        if (value === null || value === undefined) return "—";
        const n = Number(value);
        if (!Number.isFinite(n)) return "—";
        return signed && n > 0 ? `+${nf.format(n)}` : nf.format(n);
    }

    function localDate(value) {
        if (!value) return "Sin registros";
        const d = new Date(value);
        return Number.isNaN(d.getTime()) ? "Sin registros" : d.toLocaleString("es");
    }

    function dayLabel(iso) {
        return new Date(`${iso}T12:00:00Z`).toLocaleDateString("es", {
            day: "2-digit", month: "short", timeZone: "UTC"
        });
    }

    function notice(title, message, kind = "neutral") {
        const box = $("statsNotice");
        if (!box) return;
        box.className = `stats-notice ${kind}`;
        text("statsNoticeTitle", title);
        text("statsNoticeBody", message);
    }

    function tableMessage(tableBody, message, columns) {
        tableBody.replaceChildren();
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = columns;
        cell.className = "stats-table-message";
        cell.textContent = message;
        row.appendChild(cell);
        tableBody.appendChild(row);
    }

    function setEmptyChart(message) {
        const area = $("statsTrendChart");
        area.replaceChildren();
        area.style.minWidth = "0";
        const empty = document.createElement("div");
        empty.className = "stats-chart-empty";
        empty.textContent = message;
        area.appendChild(empty);
    }

    function renderDemo() {
        for (const id of ["statsEntries", "statsExits", "statsNet", "statsTotal"]) {
            text(id, "—");
        }
        for (const id of ["statsEntriesCompare", "statsExitsCompare", "statsNetCompare", "statsTotalCompare"]) {
            text(id, "Sin datos reales");
        }
        text("statsChannelName", "Canal pendiente");
        text("statsCollectorStatus", "Sin conexión");
        text("statsLastSync", "Sin registros");
        text("statsPeriodLabel", `Últimos ${$("statisticsPeriod").value} días · UTC`);
        setEmptyChart("Vista previa: conecta Telegram para visualizar movimientos reales.");
        tableMessage($("statsDailyBody"), "Los registros diarios aparecerán al conectar la Mini App.", 4);
        tableMessage($("statsEventsBody"), "Sin movimientos disponibles en modo DEMO.", 3);
        notice("Vista previa local", "No se han inventado estadísticas. La base de datos solo se consultará con autenticación válida de Telegram.");
    }

    function renderChart(daily, hasEvents) {
        if (!hasEvents) {
            setEmptyChart("No hay entradas ni salidas registradas en este período.");
            return;
        }
        const chart = $("statsTrendChart");
        chart.replaceChildren();
        chart.style.minWidth = `${Math.max(620, daily.length * 28)}px`;
        const peak = Math.max(1, ...daily.map(day => Math.max(day.entries, day.exits)));
        daily.forEach(day => {
            const column = document.createElement("div");
            column.className = "stats-bar-column";
            column.setAttribute("role", "img");
            column.setAttribute("aria-label", `${day.date}: ${day.entries} entradas, ${day.exits} salidas`);
            const pair = document.createElement("div");
            pair.className = "stats-bar-pair";
            for (const type of ["entries", "exits"]) {
                const bar = document.createElement("span");
                bar.className = `stats-bar stats-bar-${type}`;
                const value = Number(day[type]) || 0;
                bar.style.height = value === 0 ? "0" : `${Math.max(4, value / peak * 100)}%`;
                bar.title = `${dayLabel(day.date)}: ${value} ${type === "entries" ? "entradas" : "salidas"}`;
                pair.appendChild(bar);
            }
            const label = document.createElement("span");
            label.className = "stats-bar-label";
            label.textContent = dayLabel(day.date);
            column.append(pair, label);
            chart.appendChild(column);
        });
    }

    function renderDaily(daily) {
        const body = $("statsDailyBody");
        body.replaceChildren();
        [...daily].reverse().forEach(day => {
            const row = document.createElement("tr");
            const values = [dayLabel(day.date), number(day.entries), number(day.exits), number(day.net, true)];
            values.forEach((value, index) => {
                const cell = document.createElement("td");
                cell.textContent = value;
                if (index === 3) cell.className = day.net > 0 ? "stats-positive" : day.net < 0 ? "stats-negative" : "";
                row.appendChild(cell);
            });
            body.appendChild(row);
        });
    }

    function renderEvents(events) {
        const body = $("statsEventsBody");
        body.replaceChildren();
        if (!events.length) {
            tableMessage(body, "No hay movimientos registrados en este período.", 3);
            return;
        }
        events.forEach(event => {
            const row = document.createElement("tr");
            const type = document.createElement("td");
            type.textContent = event.event_type === "entry" ? "↗ Entrada" : "↙ Salida";
            type.className = event.event_type === "entry" ? "stats-positive" : "stats-negative";
            const person = document.createElement("td");
            person.textContent = event.first_name || (event.username ? `@${event.username}` : `Usuario ${event.telegram_user_id}`);
            const time = document.createElement("td");
            time.textContent = localDate(event.event_at);
            row.append(type, person, time);
            body.appendChild(row);
        });
    }

    function render(data) {
        const { period, channel, metrics, comparison, coverage, daily, recent_events } = data;
        text("statsPeriodLabel", `${period.start_date} — ${period.end_date} · UTC`);
        text("statsChannelName", channel.configured ? (channel.title || String(channel.telegram_channel_id)) : "Sin canal configurado");
        text("statsCollectorStatus", STATUS[coverage.collector_status] || coverage.collector_status);
        text("statsLastSync", localDate(coverage.last_sync_at));

        if (!channel.configured) {
            for (const id of ["statsEntries", "statsExits", "statsNet", "statsTotal"]) text(id, "—");
            for (const id of ["statsEntriesCompare", "statsExitsCompare", "statsNetCompare", "statsTotalCompare"]) text(id, "Sin canal configurado");
            setEmptyChart("Configura primero el canal principal para consultar sus estadísticas.");
            tableMessage($("statsDailyBody"), "Configura el canal principal.", 4);
            tableMessage($("statsEventsBody"), "Configura el canal principal.", 3);
            notice("Canal pendiente", "Todavía no se ha configurado el canal que debemos supervisar.", "warning");
            return;
        }

        text("statsEntries", number(metrics.entries));
        text("statsExits", number(metrics.exits));
        text("statsNet", number(metrics.net, true));
        text("statsTotal", number(metrics.total_events));
        text("statsEntriesCompare", `Cambio anterior: ${number(comparison.entries_difference, true)}`);
        text("statsExitsCompare", `Cambio anterior: ${number(comparison.exits_difference, true)}`);
        text("statsNetCompare", `Cambio anterior: ${number(comparison.net_difference, true)}`);
        text("statsTotalCompare", `${metrics.active_days} días con movimientos`);

        renderChart(daily, metrics.total_events > 0);
        renderDaily(daily);
        renderEvents(recent_events);

        if (!channel.tracking_enabled) {
            notice("Seguimiento pausado", "Los datos corresponden a eventos previamente registrados. Mientras el seguimiento esté pausado podrían faltar movimientos.", "warning");
        } else if (!coverage.history_backfill_completed) {
            notice("Cobertura pendiente", "La recuperación inicial de hasta 24 horas aún no consta como completada. Las cifras pueden estar incompletas.", "warning");
        } else {
            notice("Datos del recolector", "Se muestran únicamente movimientos efectivamente registrados en SQLite, en horario UTC. Los períodos en curso pueden no estar completos.", "success");
        }
    }

    async function refresh() {
        if (DEMO) {
            renderDemo();
            return { demo: true };
        }
        const ticket = ++sequence;
        text("statsPeriodLabel", "Consultando datos...");
        try {
            const days = Number($("statisticsPeriod").value);
            const result = await API.statistics(days);
            if (ticket === sequence) render(result);
            return result;
        } catch (error) {
            if (ticket === sequence) {
                text("statsPeriodLabel", "No se pudo actualizar");
                notice("Error al cargar estadísticas", error.message || "Error de conexión", "error");
            }
            throw error;
        }
    }

    $("statisticsPeriod")?.addEventListener("change", () => {
        refresh().catch(() => {});
    });
    $("statisticsRefreshButton")?.addEventListener("click", () => {
        refresh().catch(() => {});
    });

    window.StatisticsPanel = Object.freeze({ refresh });
    if (DEMO) renderDemo();
})();
