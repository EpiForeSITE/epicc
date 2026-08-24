(function () {
    'use strict';

    // Plotly draws to a fixed pixel size, and Streamlit redraws it from the
    // width of the element it sits in. Printing swaps the results column for a
    // full page, but that reflow lands too late for the print snapshot, so the
    // report goes to paper with column-width charts stranded on page-width
    // sheets. Laying the report out at the printable width *before* opening the
    // dialog gives Streamlit the resize it needs, in time to matter: the class
    // below is what sizes the report (see `html.epicc-printing` in the CSS).
    const PRINTING_CLASS = 'epicc-printing';
    const POLL_MS = 100;
    const NO_CHART_GRACE_MS = 600;
    const READY_TIMEOUT_MS = 2500;
    const PAINT_MS = 50;
    const RESTORE_FALLBACK_MS = 8000;

    const root = document.documentElement;

    function charts() {
        return Array.from(
            document.querySelectorAll('.st-key-results-report .js-plotly-plot')
        ).filter(function (chart) {
            return chart._fullLayout;
        });
    }

    // A chart has caught up with the print layout once it is as wide as the box
    // it was drawn into.
    function chartsReady() {
        const drawn = charts();
        if (!drawn.length) {
            return false;
        }

        return drawn.every(function (chart) {
            const box = chart.closest('[data-testid="stPlotlyChart"]');
            return box && Math.abs(chart._fullLayout.width - box.clientWidth) <= 2;
        });
    }

    // This script is rendered by the same rerun that draws the report, so the
    // charts may still be mounting; the resize is asynchronous on top of that.
    function whenReadyToPrint() {
        return new Promise(function (resolve) {
            const started = Date.now();

            (function poll() {
                const waited = Date.now() - started;
                const chartless = !charts().length && waited >= NO_CHART_GRACE_MS;

                if (chartsReady() || chartless || waited >= READY_TIMEOUT_MS) {
                    resolve();
                    return;
                }

                window.setTimeout(poll, POLL_MS);
            })();
        });
    }

    function delay(ms) {
        return new Promise(function (resolve) {
            window.setTimeout(resolve, ms);
        });
    }

    let restored = false;

    function restore() {
        if (restored) {
            return;
        }
        restored = true;
        root.classList.remove(PRINTING_CLASS);
    }

    root.classList.add(PRINTING_CLASS);

    // Undoing the print layout is armed before anything can go wrong with it:
    // not every browser fires afterprint, and the timer cannot run while a
    // print dialog is open, so the report never stays stuck at page width.
    window.addEventListener('afterprint', restore, { once: true });
    window.setTimeout(restore, RESTORE_FALLBACK_MS);

    whenReadyToPrint()
        .then(function () {
            return delay(PAINT_MS);
        })
        .then(function () {
            window.print();
        });
})();
