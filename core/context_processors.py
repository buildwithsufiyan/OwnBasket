from products.models import Category, Brand
from cart.models import Cart, CartItem


def ecommerce_context(request):
    categories = Category.objects.all()
    brands = Brand.objects.all()

    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(id=request.user.id)
        cart_count = sum(item.quantity for item in CartItem.objects.filter(cart=cart))
    else:
        cart_count = 0

    return {
        'all_categories': categories,
        'all_brands': brands,
        'cart_count': cart_count,
    }
