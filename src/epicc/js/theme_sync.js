(function () {
    const root = document.documentElement;
    const darkModeQuery = window.matchMedia("(prefers-color-scheme: dark)");

    if (root.dataset.epiccThemeSyncInstalled === "true") {
        return;
    }
    root.dataset.epiccThemeSyncInstalled = "true";

    function streamlitTheme() {
        const app = document.querySelector('[data-testid="stApp"]');
        const colorScheme = app ? getComputedStyle(app).colorScheme : "normal";

        if (colorScheme.includes("dark")) {
            return "dark";
        }
        if (colorScheme.includes("light")) {
            return "light";
        }
        return darkModeQuery.matches ? "dark" : "light";
    }

    function synchronizeTheme() {
        const theme = streamlitTheme();
        if (root.dataset.epiccTheme !== theme) {
            root.dataset.epiccTheme = theme;
            root.style.colorScheme = theme;
        }
    }

    function scheduleThemeSynchronization() {
        window.requestAnimationFrame(() => {
            window.requestAnimationFrame(synchronizeTheme);
        });
    }

    synchronizeTheme();

    const app = document.querySelector('[data-testid="stApp"]');
    if (app) {
        new MutationObserver(scheduleThemeSynchronization).observe(app, {
            attributeFilter: ["class", "style"],
            attributes: true,
        });
    }

    new MutationObserver(scheduleThemeSynchronization).observe(document.head, {
        characterData: true,
        childList: true,
        subtree: true,
    });

    document.addEventListener("click", (event) => {
        const target = event.target;
        const item = target instanceof Element
            ? target.closest('[role="menuitemradio"]')
            : null;

        if (/\b(System|Light|Dark)\s*$/.test(item?.textContent || "")) {
            scheduleThemeSynchronization();
        }
    });
    darkModeQuery.addEventListener("change", scheduleThemeSynchronization);
})();
