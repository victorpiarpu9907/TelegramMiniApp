"use strict";

(function () {

    const API = window.TelegramAPI;

    const numberFormat = new Intl.NumberFormat("es");

    function setText(element, value) {

        if (element) {
            element.textContent = value;
        }
    }


    function formatNumber(value) {

        if (value === null || value === undefined) {
            return "—";
        }

        return numberFormat.format(value);
    }


    function updateStatus(element, label, type) {

        if (!element) return;

        element.textContent = label;

        element.classList.remove(
            "neutral",
            "ready",
            "error"
        );

        element.classList.add(type);
    }


    function renderSystemStatus(summary) {

        const userbot = summary.userbot.status;

        const states = {
            running: ["Userbot conectado", "Conexión activa"],
            connecting: ["Conectando...", "Estableciendo conexión"],
            reconnecting: ["Reconectando...", "Recuperando conexión"],
            stopped: ["Userbot detenido", "Conexión detenida"],
            offline: ["Userbot desconectado", "Sin conexión"],
            error: ["Error del Userbot", "Se requiere revisión"],
            not_configured: ["Esperando configuración", "Credenciales pendientes"]
        };

        const state = states[userbot] || [
            "Estado desconocido",
            "No se pudo determinar el estado"
        ];

        setText(
            document.querySelector(".system-banner h2"),
            state[0]
        );

        setText(
            document.querySelector(".system-banner p"),
            state[1]
        );

        const bannerStatus = document.querySelector(
            ".system-banner-right span:last-child"
        );

        setText(bannerStatus, state[0]);

        const dot = document.querySelector(
            ".system-banner-right .status-dot"
        );

        if (dot) {
            dot.className = "status-dot";

            dot.classList.add(
                userbot === "running" ? "status-active" :
                userbot === "error" ? "status-error" :
                "status-neutral"
            );
        }
    }


    function renderMetrics(metrics) {

        const cards = document.querySelectorAll(
            ".metric-card"
        );

        const values = [
            metrics.current_members,
            metrics.entries_today,
            metrics.exits_today,
            metrics.net_change_today
        ];

        cards.forEach((card, index) => {

            setText(
                card.querySelector(".metric-value"),
                formatNumber(values[index])
            );

            const footer = card.querySelector(".metric-footer");

            if (footer) {
                footer.innerHTML = `
                    <span class="metric-neutral">Datos del servidor</span>
                    <span>Información actualizada</span>
                `;
            }

        });
    }


    function renderComponents(summary, health) {

        const rows = document.querySelectorAll(
            ".component-row"
        );

        if (rows.length < 4) return;

        const userbot = summary.userbot.status;
        const collector = summary.event_collector.status;
        const database = health.database;
        const channel = summary.channel;

        updateStatus(
            rows[0].querySelector(".component-status"),
            userbot === "running" ? "Conectado" :
            userbot === "error" ? "Error" :
            userbot === "not_configured" ? "Sin configurar" :
            "Desconectado",
            userbot === "running" ? "ready" :
            userbot === "error" ? "error" : "neutral"
        );

        updateStatus(
            rows[1].querySelector(".component-status"),
            collector === "running" ? "Activo" :
            collector === "error" ? "Error" :
            collector === "waiting_for_channel" ? "Esperando canal" :
            collector === "paused" ? "Pausado" :
            "Pendiente",
            collector === "running" ? "ready" :
            collector === "error" ? "error" : "neutral"
        );

        updateStatus(
            rows[2].querySelector(".component-status"),
            database === "connected" ? "Conectada" : "Error",
            database === "connected" ? "ready" : "error"
        );

        updateStatus(
            rows[3].querySelector(".component-status"),
            !channel.configured ? "Sin configurar" :
            channel.enabled ? "Configurado" : "Pausado",
            channel.configured && channel.enabled
                ? "ready" : "neutral"
        );
    }


    function renderActivity(items) {

        const panel = document.querySelector(
            ".activity-panel"
        );

        if (!panel) return;

        const empty = panel.querySelector(".activity-empty");

        let list = panel.querySelector(".activity-list");

        if (!items || items.length === 0) {

            if (empty) empty.style.display = "flex";
            if (list) list.remove();

            return;
        }

        if (empty) empty.style.display = "none";

        if (!list) {

            list = document.createElement("div");
            list.className = "activity-list";

            panel.appendChild(list);
        }

        list.replaceChildren();

        items.forEach(item => {

            const row = document.createElement("div");
            row.className = "activity-item";

            const indicator = document.createElement("span");
            indicator.className = `activity-indicator ${item.severity.toLowerCase()}`;

            const content = document.createElement("div");
            content.className = "activity-item-content";

            const message = document.createElement("strong");
            message.textContent = item.message;

            const category = document.createElement("span");
            category.textContent = item.category;

            const date = document.createElement("time");
            date.textContent = item.created_at
                ? new Date(item.created_at).toLocaleString("es")
                : "";

            content.append(message, category);

            row.append(indicator, content, date);

            list.appendChild(row);

        });
    }


    function renderChart(items) {

        const chart = document.querySelector(".chart-empty");

        if (!chart) return;

        if (!items || items.length === 0) return;

        chart.replaceChildren();
        chart.classList.add("chart-has-data");

        const maxValue = Math.max(
            1,
            ...items.flatMap(item => [
                item.entries,
                item.exits
            ])
        );

        items.forEach(item => {

            const column = document.createElement("div");
            column.className = "chart-column";

            const bars = document.createElement("div");
            bars.className = "chart-bars";

            const entryBar = document.createElement("div");
            entryBar.className = "chart-bar entry";
            entryBar.style.height =
                `${Math.max(2, item.entries / maxValue * 100)}%`;
            entryBar.title = `Entradas: ${item.entries}`;

            const exitBar = document.createElement("div");
            exitBar.className = "chart-bar exit";
            exitBar.style.height =
                `${Math.max(2, item.exits / maxValue * 100)}%`;
            exitBar.title = `Salidas: ${item.exits}`;

            bars.append(entryBar, exitBar);

            const label = document.createElement("span");
            label.className = "chart-day-label";

            label.textContent = new Date(
                `${item.date}T12:00:00`
            ).toLocaleDateString("es", {
                weekday: "short"
            });

            column.append(bars, label);
            chart.appendChild(column);

        });
    }


    async function refresh() {

        const [summary, health] = await Promise.all([
            API.dashboardSummary(),
            API.health()
        ]);

        renderSystemStatus(summary);
        renderMetrics(summary.metrics);
        renderComponents(summary, health);
        renderActivity(summary.recent_activity);
        renderChart(summary.trend_7_days);

        return summary;
    }


    async function initialize() {

        const webApp = window.Telegram?.WebApp;

        if (webApp) {
            webApp.ready();
            webApp.expand();
        }

        if (window.APP_CONFIG?.DEMO_MODE) {
            return { demo: true };
        }

        const auth = await API.authenticate();

        const profile = document.querySelector(
            ".profile-info strong"
        );

        if (profile && auth.user?.first_name) {
            profile.textContent = auth.user.first_name;
        }

        return refresh();
    }


    window.Dashboard = Object.freeze({
        initialize,
        refresh
    });

})();
