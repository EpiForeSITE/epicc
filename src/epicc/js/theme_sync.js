(function () {
    const root = document.documentElement;
    const darkModeQuery = window.matchMedia("(prefers-color-scheme: dark)");

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

    if (root.__epiccThemeSyncInterval) {
        window.clearInterval(root.__epiccThemeSyncInterval);
    }

    synchronizeTheme();
    root.__epiccThemeSyncInterval = window.setInterval(synchronizeTheme, 100);
})();
