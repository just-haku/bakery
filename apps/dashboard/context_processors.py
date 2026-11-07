from .models import StoreSetting
from apps.products.models import Category
from apps.custom_orders.models import CustomCakeOrder, CakeOrderStatus

def store_context(request):
    try:
        setting = StoreSetting.get_settings()
    except Exception:
        setting = None

    categories = Category.objects.filter(is_active=True)
    pending_cakes_count = 0
    try:
        pending_cakes_count = CustomCakeOrder.objects.filter(
            status__in=[CakeOrderStatus.RECEIVED, CakeOrderStatus.BAKING]
        ).count()
    except Exception:
        pass

    user_profile = None
    if request.user.is_authenticated and hasattr(request.user, 'customer_profile'):
        user_profile = request.user.customer_profile

    return {
        'store_setting': setting,
        'global_categories': categories,
        'pending_cakes_count': pending_cakes_count,
        'current_customer_profile': user_profile,
        'current_portal_role': getattr(request, 'portal_role', 'ADMIN'),
    }
