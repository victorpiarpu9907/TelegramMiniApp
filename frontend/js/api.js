"use strict";

(function () {

    const config = window.APP_CONFIG || {};

    const API_BASE_URL = (config.API_BASE_URL || "")
        .replace(/\/+$/, "");

    const REQUEST_TIMEOUT_MS = config.REQUEST_TIMEOUT_MS || 12000;

    let accessToken = null;
    let tokenExpiresAt = 0;
    let authPromise = null;


    function getTelegramWebApp() {
        return window.Telegram?.WebApp || null;
    }


    function getInitData() {

        const webApp = getTelegramWebApp();

        return webApp?.initData || "";
    }


    async function request(path, options = {}) {

        if (!API_BASE_URL) {
            throw new Error("La dirección del backend no está configurada.");
        }

        const requiresAuth = options.auth !== false;

        if (requiresAuth) {
            await authenticate();
        }

        const controller = new AbortController();

        const timeout = setTimeout(
            () => controller.abort(),
            REQUEST_TIMEOUT_MS
        );

        const headers = {
            Accept: "application/json",
            ...(options.headers || {})
        };

        if (options.body !== undefined) {
            headers["Content-Type"] = "application/json";
        }

        if (requiresAuth) {
            headers.Authorization = `Bearer ${accessToken}`;
        }

        try {

            let response = await fetch(
                `${API_BASE_URL}${path}`,
                {
                    method: options.method || "GET",
                    headers,
                    body: options.body === undefined
                        ? undefined
                        : JSON.stringify(options.body),
                    signal: controller.signal
                }
            );

            // Renovar el token si expiró y volver a intentar.
            if (response.status === 401 && requiresAuth) {

                accessToken = null;
                tokenExpiresAt = 0;

                await authenticate();

                headers.Authorization = `Bearer ${accessToken}`;

                response = await fetch(
                    `${API_BASE_URL}${path}`,
                    {
                        method: options.method || "GET",
                        headers,
                        body: options.body === undefined
                            ? undefined
                            : JSON.stringify(options.body),
                        signal: controller.signal
                    }
                );
            }

            const data = await response.json().catch(() => ({}));

            if (!response.ok) {

                throw new Error(
                    data.detail || `Error HTTP ${response.status}`
                );
            }

            return data;

        } catch (error) {

            if (error.name === "AbortError") {
                throw new Error("El servidor tardó demasiado en responder.");
            }

            throw error;

        } finally {

            clearTimeout(timeout);

        }
    }


    async function authenticate() {

        if (
            accessToken &&
            Date.now() < tokenExpiresAt - 30000
        ) {
            return true;
        }

        if (authPromise) {
            return authPromise;
        }

        authPromise = (async () => {

            const initData = getInitData();

            if (!initData) {
                throw new Error(
                    "Abre esta aplicación desde Telegram para autenticarte."
                );
            }

            const data = await request("/api/auth/telegram", {
                method: "POST",
                auth: false,
                body: {
                    init_data: initData
                }
            });

            accessToken = data.access_token;

            tokenExpiresAt = Date.now() +
                (data.expires_in * 1000);

            return data;

        })();

        try {
            return await authPromise;
        } finally {
            authPromise = null;
        }
    }


    const API = {

        authenticate,

        health() {
            return request("/health", {
                auth: false
            });
        },

        dashboardSummary() {
            return request("/api/dashboard/summary");
        },

        statistics(days = 7) {
            return request(`/api/statistics/summary?days=${days}`);
        },

        recentActivity(limit = 20) {
            return request(
                `/api/dashboard/activity?limit=${limit}`
            );
        },

        automations() {
            return request("/api/automations");
        },

        userbotStatus() {
            return request("/api/userbot/status");
        },

        channel() {
            return request("/api/channel");
        },

        updateChannel(payload) {
            return request("/api/channel", {
                method: "PUT",
                body: payload
            });
        },

        updateTracking(enabled) {
            return request("/api/channel/tracking", {
                method: "PATCH",
                body: { enabled }
            });
        },

        updateAutomation(key, enabled) {
            return request(`/api/automations/${encodeURIComponent(key)}`, {
                method: "PATCH",
                body: { enabled }
            });
        },

        startUserbot() {
            return request("/api/userbot/start", {
                method: "POST"
            });
        },

        stopUserbot() {
            return request("/api/userbot/stop", {
                method: "POST"
            });
        }

    };


    window.TelegramAPI = Object.freeze(API);

})();
