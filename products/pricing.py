from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Q
from django.utils import timezone

from .models import (
    BuyXGetYOffer,
    CategoryDiscount,
    Coupon,
    CouponRedemption,
    DiscountType,
    FlashSale,
    FreeShippingOffer,
    ProductDiscount,
)


MONEY_ZERO = Decimal('0.00')
STANDARD_SHIPPING_AMOUNT = Decimal('79.00')


@dataclass
class ProductPricing:
    original_price: Decimal
    final_price: Decimal
    discount_amount: Decimal = MONEY_ZERO
    compare_at_price: Decimal | None = None
    badge_text: str = ''
    source_type: str = 'none'
    source_name: str = ''
    source_priority: int = 0
    flash_sale_end_at: object = None

    @property
    def has_discount(self):
        return self.discount_amount > MONEY_ZERO

    @property
    def discount_percent(self):
        if not self.compare_at_price or self.compare_at_price <= MONEY_ZERO:
            return 0
        return int(
            ((self.discount_amount / self.compare_at_price) * Decimal('100'))
            .quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        )


@dataclass
class CartLinePricing:
    item: object
    pricing: ProductPricing
    quantity: int
    unit_original_price: Decimal
    unit_final_price: Decimal
    line_original_total: Decimal
    line_final_total: Decimal
    line_discount_total: Decimal

    @property
    def has_item_discount(self):
        return self.line_discount_total > MONEY_ZERO


@dataclass
class CartSummary:
    items: list
    line_items: list
    item_count: int
    subtotal_original: Decimal
    item_discount_total: Decimal
    subtotal_after_item_discounts: Decimal
    coupon_discount: Decimal
    buy_x_get_y_discount: Decimal
    shipping_amount: Decimal
    shipping_savings: Decimal
    grand_total: Decimal
    applied_coupon: Coupon | None
    coupon_message: str
    applied_free_shipping_offer: object = None
    buy_x_get_y_messages: list | None = None

    @property
    def total_discount(self):
        return _money(self.item_discount_total + self.coupon_discount + self.buy_x_get_y_discount)


def _money(value):
    if value is None:
        value = MONEY_ZERO
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _is_active_window(rule, at_time):
    if not rule.is_active:
        return False
    if rule.start_at and rule.start_at > at_time:
        return False
    if rule.end_at and rule.end_at < at_time:
        return False
    return True


def _calculate_discount_amount(discount_type, value, price, max_discount_amount=None):
    price = _money(price)
    value = _money(value)

    if discount_type == DiscountType.PERCENTAGE:
        discount_amount = price * value / Decimal('100')
    else:
        discount_amount = value

    if max_discount_amount:
        discount_amount = min(discount_amount, _money(max_discount_amount))

    if discount_amount > price:
        discount_amount = price

    return _money(discount_amount)


def _base_price(product):
    compare_price = product.mrp or product.old_price
    sell_price = product.selling_price or product.price
    if compare_price and sell_price and compare_price > sell_price:
        return _money(compare_price)
    return _money(sell_price or compare_price or MONEY_ZERO)


def _default_badge(percent):
    if not percent:
        return ''
    return f"{percent}% OFF"


def build_discount_index(products, at_time=None):
    products = list(products)
    at_time = at_time or timezone.now()
    product_ids = [product.id for product in products]
    category_ids = list({product.category_id for product in products})

    product_rules_map = defaultdict(list)
    for rule in ProductDiscount.objects.filter(product_id__in=product_ids):
        if _is_active_window(rule, at_time):
            product_rules_map[rule.product_id].append(rule)

    category_rules_map = defaultdict(list)
    for rule in CategoryDiscount.objects.filter(category_id__in=category_ids):
        if _is_active_window(rule, at_time):
            category_rules_map[rule.category_id].append(rule)

    flash_product_map = defaultdict(list)
    flash_category_map = defaultdict(list)
    flash_sales = FlashSale.objects.filter(
        is_active=True,
    ).filter(
        Q(start_at__isnull=True) | Q(start_at__lte=at_time),
        Q(end_at__gte=at_time),
    ).prefetch_related('products', 'categories')
    for sale in flash_sales:
        for product_id in sale.products.values_list('id', flat=True):
            if product_id in product_ids:
                flash_product_map[product_id].append(sale)
        for category_id in sale.categories.values_list('id', flat=True):
            if category_id in category_ids:
                flash_category_map[category_id].append(sale)

    return {
        'product_rules_map': product_rules_map,
        'category_rules_map': category_rules_map,
        'flash_product_map': flash_product_map,
        'flash_category_map': flash_category_map,
        'resolved_at': at_time,
    }


def resolve_product_pricing(product, discount_index=None):
    if discount_index is None:
        discount_index = build_discount_index([product])

    base_price = _base_price(product)
    product_candidates = []
    category_candidates = []

    if getattr(product, 'discount_price', None) and product.has_active_offer():
        final_price = _money(product.discount_price)
        manual_discount = _money(base_price - final_price)
        if manual_discount > MONEY_ZERO:
            product_candidates.append({
                'final_price': final_price,
                'discount_amount': manual_discount,
                'badge_text': 'Offer Price',
                'source_type': 'product',
                'source_name': 'Scheduled Product Offer',
                'priority': 310,
                'flash_sale_end_at': product.offer_end_at,
            })

    if product.old_price and product.old_price > product.price:
        final_price = _money(product.price)
        manual_discount = _money(base_price - final_price)
        if manual_discount > MONEY_ZERO:
            product_candidates.append({
                'final_price': final_price,
                'discount_amount': manual_discount,
                'badge_text': 'Sale',
                'source_type': 'product',
                'source_name': 'Manual Sale Price',
                'priority': 300,
                'flash_sale_end_at': None,
            })

    for rule in discount_index['product_rules_map'].get(product.id, []):
        discount_amount = _calculate_discount_amount(
            rule.discount_type,
            rule.value,
            base_price,
            rule.max_discount_amount,
        )
        final_price = _money(base_price - discount_amount)
        product_candidates.append({
            'final_price': final_price,
            'discount_amount': discount_amount,
            'badge_text': rule.badge_text,
            'source_type': 'product',
            'source_name': rule.name,
            'priority': rule.priority or 300,
            'flash_sale_end_at': None,
        })

    for sale in discount_index['flash_product_map'].get(product.id, []):
        discount_amount = _calculate_discount_amount(
            sale.discount_type,
            sale.value,
            base_price,
            sale.max_discount_amount,
        )
        final_price = _money(base_price - discount_amount)
        product_candidates.append({
            'final_price': final_price,
            'discount_amount': discount_amount,
            'badge_text': sale.badge_text or 'Flash Sale',
            'source_type': 'flash_sale',
            'source_name': sale.name,
            'priority': sale.priority or 350,
            'flash_sale_end_at': sale.end_at,
        })

    for sale in discount_index['flash_category_map'].get(product.category_id, []):
        discount_amount = _calculate_discount_amount(
            sale.discount_type,
            sale.value,
            base_price,
            sale.max_discount_amount,
        )
        final_price = _money(base_price - discount_amount)
        category_candidates.append({
            'final_price': final_price,
            'discount_amount': discount_amount,
            'badge_text': sale.badge_text or 'Flash Sale',
            'source_type': 'flash_sale',
            'source_name': sale.name,
            'priority': sale.priority or 320,
            'flash_sale_end_at': sale.end_at,
        })

    for rule in discount_index['category_rules_map'].get(product.category_id, []):
        discount_amount = _calculate_discount_amount(
            rule.discount_type,
            rule.value,
            base_price,
            rule.max_discount_amount,
        )
        final_price = _money(base_price - discount_amount)
        category_candidates.append({
            'final_price': final_price,
            'discount_amount': discount_amount,
            'badge_text': rule.badge_text,
            'source_type': 'category',
            'source_name': rule.name,
            'priority': rule.priority or 200,
            'flash_sale_end_at': None,
        })

    product_choice = _choose_best_candidate(product_candidates)
    category_choice = _choose_best_candidate(category_candidates)
    chosen = product_choice or category_choice

    if not chosen:
        return ProductPricing(
            original_price=_money(product.selling_price or product.price),
            final_price=_money(product.selling_price or product.price),
        )

    compare_at_price = base_price if chosen['final_price'] < base_price else None
    pricing = ProductPricing(
        original_price=base_price,
        final_price=chosen['final_price'],
        discount_amount=_money(chosen['discount_amount']),
        compare_at_price=compare_at_price,
        badge_text=chosen['badge_text'],
        source_type=chosen['source_type'],
        source_name=chosen['source_name'],
        source_priority=chosen['priority'],
        flash_sale_end_at=chosen['flash_sale_end_at'],
    )
    if not pricing.badge_text:
        pricing.badge_text = _default_badge(pricing.discount_percent)
    return pricing


def _choose_best_candidate(candidates):
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda candidate: (
            candidate['discount_amount'],
            candidate['priority'],
            candidate['final_price'] * Decimal('-1'),
        ),
        reverse=True,
    )[0]


def attach_pricing_to_products(products):
    products = list(products)
    discount_index = build_discount_index(products)
    for product in products:
        pricing = resolve_product_pricing(product, discount_index=discount_index)
        _apply_pricing_fields(product, pricing)
    return products


def _apply_pricing_fields(product, pricing):
    product.pricing = pricing
    product.display_price = pricing.final_price
    product.display_compare_price = pricing.compare_at_price
    product.display_badge = pricing.badge_text
    product.display_discount_percent = pricing.discount_percent
    product.has_display_discount = pricing.has_discount
    product.flash_sale_end_at = pricing.flash_sale_end_at
    product.display_discount_source = pricing.source_name
    return product


def get_coupon_by_code(code):
    normalized_code = (code or '').upper().strip()
    if not normalized_code:
        return None
    return Coupon.objects.filter(code=normalized_code).first()


def validate_coupon(coupon, user=None, subtotal=MONEY_ZERO, eligible_subtotal=MONEY_ZERO):
    if not coupon:
        return False, 'Enter a valid coupon code.'
    now = timezone.now()
    if not _is_active_window(coupon, now):
        return False, 'This coupon is inactive or expired.'
    subtotal = _money(subtotal)
    eligible_subtotal = _money(eligible_subtotal)
    if subtotal < _money(coupon.min_order_amount):
        return False, f"Minimum order amount for {coupon.code} is Rs. {coupon.min_order_amount}."
    if eligible_subtotal <= MONEY_ZERO and not coupon.free_shipping:
        return False, 'This coupon cannot be applied on already discounted items.'
    if user and coupon.first_order_only:
        from orders.models import Order

        if Order.objects.filter(user=user).exists():
            return False, 'This coupon is only valid on the first order.'
    if coupon.usage_limit is not None and coupon.redemptions.count() >= coupon.usage_limit:
        return False, 'This coupon has reached its usage limit.'
    if user and coupon.usage_per_user is not None:
        user_redemptions = CouponRedemption.objects.filter(coupon=coupon, user=user).count()
        if user_redemptions >= coupon.usage_per_user:
            return False, 'You have already used this coupon the maximum number of times.'
    return True, f"Coupon {coupon.code} applied successfully."


def calculate_coupon_discount(coupon, eligible_subtotal):
    eligible_subtotal = _money(eligible_subtotal)
    if not coupon or eligible_subtotal <= MONEY_ZERO:
        return MONEY_ZERO
    return _calculate_discount_amount(
        coupon.discount_type,
        coupon.value,
        eligible_subtotal,
        coupon.max_discount_amount,
    )


def _matches_offer_target(item, *, product_id=None, category_id=None):
    if product_id:
        return item.product_id == product_id
    if category_id:
        return item.product.category_id == category_id
    return False


def calculate_buy_x_get_y_discount(items, line_items):
    active_offers = [
        offer for offer in BuyXGetYOffer.objects.all()
        if offer.is_currently_active
    ]
    if not active_offers:
        return MONEY_ZERO, []

    remaining_quantities = {
        line.item.id: line.quantity for line in line_items
    }
    total_discount = MONEY_ZERO
    messages = []

    for offer in active_offers:
        buy_qty = sum(
            item.quantity
            for item in items
            if _matches_offer_target(
                item,
                product_id=offer.buy_product_id,
                category_id=offer.buy_category_id,
            )
        )
        eligible_free_units = (buy_qty // offer.buy_quantity) * offer.get_quantity
        if eligible_free_units <= 0:
            continue

        matching_lines = [
            line for line in line_items
            if _matches_offer_target(
                line.item,
                product_id=offer.get_product_id,
                category_id=offer.get_category_id,
            )
        ]
        matching_lines.sort(key=lambda line: line.unit_final_price)
        offer_discount = MONEY_ZERO

        for line in matching_lines:
            if eligible_free_units <= 0:
                break
            available_units = remaining_quantities.get(line.item.id, 0)
            if available_units <= 0:
                continue
            free_units = min(available_units, eligible_free_units)
            if free_units <= 0:
                continue
            offer_discount += _money(line.unit_final_price * free_units)
            remaining_quantities[line.item.id] = available_units - free_units
            eligible_free_units -= free_units

        if offer_discount > MONEY_ZERO:
            total_discount += offer_discount
            messages.append(f"{offer.name} saved Rs. {offer_discount}")

    return _money(total_discount), messages


def resolve_shipping(subtotal_after_discounts, coupon=None):
    subtotal_after_discounts = _money(subtotal_after_discounts)
    if subtotal_after_discounts <= MONEY_ZERO:
        return MONEY_ZERO, MONEY_ZERO, None

    if coupon and coupon.free_shipping:
        return MONEY_ZERO, STANDARD_SHIPPING_AMOUNT, f"Coupon {coupon.code} unlocked free shipping."

    offers = [
        offer for offer in FreeShippingOffer.objects.all()
        if offer.is_currently_active and subtotal_after_discounts >= _money(offer.min_order_amount)
    ]
    if offers:
        best_offer = sorted(offers, key=lambda offer: offer.min_order_amount, reverse=True)[0]
        return MONEY_ZERO, STANDARD_SHIPPING_AMOUNT, best_offer

    return STANDARD_SHIPPING_AMOUNT, MONEY_ZERO, None


def build_cart_summary(items, user=None, coupon_code=''):
    items = list(items)
    products = [item.product for item in items]
    discount_index = build_discount_index(products) if products else build_discount_index([])
    line_items = []
    subtotal_original = MONEY_ZERO
    item_discount_total = MONEY_ZERO
    subtotal_after_item_discounts = MONEY_ZERO

    for item in items:
        pricing = resolve_product_pricing(item.product, discount_index=discount_index)
        _apply_pricing_fields(item.product, pricing)
        quantity = item.quantity or 0
        line_original_total = _money(pricing.original_price * quantity)
        line_final_total = _money(pricing.final_price * quantity)
        line_discount_total = _money(line_original_total - line_final_total)
        line = CartLinePricing(
            item=item,
            pricing=pricing,
            quantity=quantity,
            unit_original_price=pricing.original_price,
            unit_final_price=pricing.final_price,
            line_original_total=line_original_total,
            line_final_total=line_final_total,
            line_discount_total=line_discount_total,
        )
        item.line_pricing = line
        line_items.append(line)
        subtotal_original += line_original_total
        item_discount_total += line_discount_total
        subtotal_after_item_discounts += line_final_total

    coupon = get_coupon_by_code(coupon_code)
    coupon_eligible_subtotal = sum(
        (
            line.line_final_total
            for line in line_items
            if not line.has_item_discount and _line_matches_coupon(line, coupon)
        ),
        MONEY_ZERO,
    )
    coupon_is_valid, coupon_message = validate_coupon(
        coupon,
        user=user,
        subtotal=subtotal_after_item_discounts,
        eligible_subtotal=coupon_eligible_subtotal,
    ) if coupon_code else (False, '')

    coupon_discount = (
        calculate_coupon_discount(coupon, coupon_eligible_subtotal)
        if coupon_is_valid else MONEY_ZERO
    )
    buy_x_get_y_discount, buy_x_get_y_messages = calculate_buy_x_get_y_discount(items, line_items)

    discounted_subtotal = _money(subtotal_after_item_discounts - coupon_discount - buy_x_get_y_discount)
    shipping_amount, shipping_savings, free_shipping_offer = resolve_shipping(
        discounted_subtotal,
        coupon=coupon if coupon_is_valid else None,
    )
    grand_total = _money(discounted_subtotal + shipping_amount)
    if grand_total < MONEY_ZERO:
        grand_total = MONEY_ZERO

    return CartSummary(
        items=items,
        line_items=line_items,
        item_count=sum(item.quantity for item in items),
        subtotal_original=_money(subtotal_original),
        item_discount_total=_money(item_discount_total),
        subtotal_after_item_discounts=_money(subtotal_after_item_discounts),
        coupon_discount=_money(coupon_discount),
        buy_x_get_y_discount=_money(buy_x_get_y_discount),
        shipping_amount=_money(shipping_amount),
        shipping_savings=_money(shipping_savings),
        grand_total=grand_total,
        applied_coupon=coupon if coupon_is_valid else None,
        coupon_message=coupon_message if coupon_is_valid else (coupon_message or ''),
        applied_free_shipping_offer=free_shipping_offer,
        buy_x_get_y_messages=buy_x_get_y_messages,
    )


def _line_matches_coupon(line, coupon):
    if not coupon:
        return True
    if coupon.category_id and line.item.product.category_id != coupon.category_id:
        return False
    if coupon.brand_id and line.item.product.brand_id != coupon.brand_id:
        return False
    return True
