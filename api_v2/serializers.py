from products.pricing import resolve_product_pricing


def money(value):
    return f'{value or 0:.2f}'


def media_url(request, field):
    if not field:
        return None
    return request.build_absolute_uri(field.url)


def product_data(request, product):
    pricing = getattr(product, 'pricing', None) or resolve_product_pricing(product)
    return {
        'id': product.pk,
        'slug': product.slug,
        'name': product.name,
        'shortDescription': product.short_description,
        'price': money(pricing.final_price),
        'compareAtPrice': money(pricing.compare_at_price) if pricing.compare_at_price else None,
        'discountPercent': pricing.discount_percent,
        'badge': pricing.badge_text,
        'currency': 'INR',
        'stock': product.stock,
        'isAvailable': product.is_active and product.stock > 0,
        'rating': str(product.rating),
        'reviewCount': product.reviews_count,
        'image': media_url(request, product.image),
        'category': {'id': product.category_id, 'name': product.category.name, 'slug': product.category.slug},
        'brand': {'id': product.brand_id, 'name': product.brand.name},
        'seller': ({'id': product.seller_id, 'name': product.seller.store_name} if product.seller_id else None),
        'url': request.build_absolute_uri(product.get_absolute_url()),
    }


def category_data(request, category):
    return {
        'id': category.pk, 'name': category.name, 'slug': category.slug,
        'image': media_url(request, category.category_image),
        'url': request.build_absolute_uri(category.target_url),
    }


def brand_data(request, brand):
    return {
        'id': brand.pk, 'name': brand.name, 'logo': media_url(request, brand.logo),
        'url': request.build_absolute_uri(brand.target_url),
    }


def review_data(review):
    return {
        'id': review.pk, 'rating': review.rating, 'title': review.title, 'body': review.body,
        'author': review.user.first_name or 'Verified customer',
        'createdAt': review.created_at.isoformat(),
    }


def order_data(request, order, *, detail=False):
    payload = {
        'id': order.pk, 'status': order.status, 'paymentMethod': order.payment_method,
        'paymentStatus': order.payment_status, 'total': money(order.total_price),
        'currency': 'INR', 'createdAt': order.created_at.isoformat(),
        'url': request.build_absolute_uri(f'/my-orders/{order.pk}/'),
    }
    if detail:
        payload.update({
            'fullName': order.full_name, 'email': order.email, 'address': order.address,
            'subtotal': money(order.subtotal), 'discount': money(order.discount_total),
            'shipping': money(order.shipping_amount), 'couponCode': order.coupon_code or '',
            'items': [{
                'id': item.pk, 'productId': item.product_id, 'name': item.product.name,
                'quantity': item.quantity, 'price': money(item.price),
                'size': item.size, 'color': item.color,
                'image': media_url(request, item.product.image),
            } for item in order.items.all()],
        })
    return payload
