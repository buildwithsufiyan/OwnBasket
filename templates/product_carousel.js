document.addEventListener('DOMContentLoaded', function () {
    const carousels = document.querySelectorAll('.product-carousel');

    carousels.forEach(function(carousel) {
        const container = carousel.closest('.product-carousel-shell');
        if (!container) return;

        const swiper = new Swiper(carousel, {
            // Optional parameters
            loop: false,
            lazy: true,
            
            // Responsive breakpoints
            slidesPerView: 1.2,
            spaceBetween: 12,
            breakpoints: {
                576: { // Small devices (landscape phones)
                    slidesPerView: 2,
                    spaceBetween: 16
                },
                768: { // Tablets
                    slidesPerView: 3,
                    spaceBetween: 20
                },
                992: { // Laptops
                    slidesPerView: 5,
                    spaceBetween: 24
                },
                1200: { // Desktops
                    slidesPerView: 6,
                    spaceBetween: 24
                }
            },

            // Navigation
            navigation: {
                nextEl: container.querySelector('.swiper-button-next'),
                prevEl: container.querySelector('.swiper-button-prev'),
            },

            // Pagination
            pagination: {
                el: container.querySelector('.swiper-pagination'),
                clickable: true,
            },

            // Accessibility
            a11y: {
                prevSlideMessage: 'Previous slide',
                nextSlideMessage: 'Next slide',
            },
        });
    });
});