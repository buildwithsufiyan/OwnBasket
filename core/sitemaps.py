from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from products.models import Brand, Category, Product


class ProductSitemap(Sitemap):
    def items(self):
        return Product.objects.marketplace_visible().filter(
            is_active=True, category__is_active=True, brand__is_active=True
        ).only("slug", "created_at").order_by("pk")

    def lastmod(self, obj):
        return obj.created_at

    def location(self, obj):
        return obj.get_absolute_url()


class CategorySitemap(Sitemap):
    def items(self):
        return Category.objects.filter(is_active=True).only("slug").order_by("pk")

    def location(self, obj):
        return reverse("products:category_detail", args=[obj.slug])


class BrandSitemap(Sitemap):
    def items(self):
        return Brand.objects.filter(is_active=True).only("pk").order_by("pk")

    def location(self, obj):
        return reverse("products:brand_detail", args=[obj.pk])


class StaticSitemap(Sitemap):
    def items(self):
        return ("landing", "home", "products:product_list", "products:category_list", "products:brand_list")

    def location(self, item):
        return reverse(item)


sitemaps = {
    "products": ProductSitemap,
    "categories": CategorySitemap,
    "brands": BrandSitemap,
    "static": StaticSitemap,
}
