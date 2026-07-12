(function () {
    function initProductCarousels() {
        if (!window.Swiper) return;
        var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        document.querySelectorAll("[data-product-carousel]").forEach(function (element) {
            if (element.dataset.initialized === "true") return;
            var shell = element.closest(".pc-shell");
            var slideCount = element.querySelectorAll(".swiper-slide").length;
            var autoplayEnabled = element.dataset.autoplay === "true" && !reducedMotion;
            var swiper = new Swiper(element, {
                slidesPerView: 1.15,
                spaceBetween: 14,
                watchOverflow: true,
                loop: element.dataset.loop === "true" && slideCount > 4,
                speed: reducedMotion ? 0 : 350,
                keyboard: { enabled: true, onlyInViewport: true },
                autoplay: autoplayEnabled ? { delay: Number(element.dataset.speed) || 4500, disableOnInteraction: false, pauseOnMouseEnter: true } : false,
                navigation: element.dataset.navigation === "true" ? { nextEl: shell.querySelector(".pc-next"), prevEl: shell.querySelector(".pc-prev") } : false,
                pagination: element.dataset.pagination === "true" ? { el: shell.querySelector(".pc-pagination"), clickable: true } : false,
                breakpoints: {
                    421: { slidesPerView: 1.4, spaceBetween: 14 },
                    576: { slidesPerView: 2, spaceBetween: 16 },
                    768: { slidesPerView: 2.5, spaceBetween: 16 },
                    992: { slidesPerView: 4, spaceBetween: 18 }
                }
            });
            document.addEventListener("visibilitychange", function () {
                if (!autoplayEnabled) return;
                document.hidden ? swiper.autoplay.stop() : swiper.autoplay.start();
            });
            element.dataset.initialized = "true";
        });
    }
    document.addEventListener("DOMContentLoaded", initProductCarousels);
}());
