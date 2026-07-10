(function () {
    function initProductCarousels() {
        if (typeof Splide === "undefined") {
            return;
        }

        document.querySelectorAll("[data-product-carousel]").forEach(function (carousel) {
            if (carousel.dataset.initialized === "true") {
                return;
            }

            var section = carousel.closest(".bb-product-section");
            var prevButton = section ? section.querySelector(".bb-carousel-prev") : null;
            var nextButton = section ? section.querySelector(".bb-carousel-next") : null;

            var splide = new Splide(carousel, {
                type: "loop",
                perPage: 6,
                perMove: 1,
                gap: "16px",
                arrows: false,
                pagination: false,
                drag: true,
                speed: 650,
                easing: "cubic-bezier(0.22, 1, 0.36, 1)",
                autoplay: true,
                interval: 4200,
                pauseOnHover: true,
                pauseOnFocus: true,
                breakpoints: {
                    1399: { perPage: 5 },
                    1199: { perPage: 4 },
                    991: { perPage: 3 },
                    575: { perPage: 2, gap: "12px" }
                }
            });

            if (prevButton) {
                prevButton.addEventListener("click", function () {
                    splide.go("<");
                });
            }

            if (nextButton) {
                nextButton.addEventListener("click", function () {
                    splide.go(">");
                });
            }

            splide.mount();
            carousel.dataset.initialized = "true";
        });
    }

    document.addEventListener("DOMContentLoaded", initProductCarousels);
}());
