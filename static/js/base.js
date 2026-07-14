(function () {
    "use strict";
    function formatRemaining(ms) {
        if (ms <= 0) return "Offer ended";
        var total = Math.floor(ms / 1000);
        var days = Math.floor(total / 86400);
        var hours = Math.floor((total % 86400) / 3600);
        var minutes = Math.floor((total % 3600) / 60);
        var seconds = total % 60;
        if (days > 0) return days + "d " + hours + "h left";
        if (hours > 0) return hours + "h " + minutes + "m left";
        return minutes + "m " + seconds + "s left";
    }
    document.addEventListener("DOMContentLoaded", function () {
        var elements = document.querySelectorAll("[data-countdown]");
        if (!elements.length) return;
        function update() {
            elements.forEach(function (element) {
                var target = new Date(element.dataset.countdown);
                if (!Number.isNaN(target.getTime())) element.textContent = formatRemaining(target.getTime() - Date.now());
            });
        }
        update();
        window.setInterval(update, 1000);
    });
}());
