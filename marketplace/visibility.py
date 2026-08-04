from django.db.models import Q

APPROVED_SELLER_STATUS = 'approved'


def visible_seller_q(prefix='seller'):
    """Match rows sold by the house store (no seller) or by an approved seller.

    ``prefix`` is the lookup path to the ``SellerProfile`` relation, for example
    ``'product__seller'`` from a cart item or ``'seller'`` from a product.
    """
    return Q(**{f'{prefix}__isnull': True}) | Q(**{f'{prefix}__verification_status': APPROVED_SELLER_STATUS})
