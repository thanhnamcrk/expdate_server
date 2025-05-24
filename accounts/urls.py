from django.urls import path
from .views import RegisterView, LoginView
from .item_views import ItemCreateView, ItemListByGroupView, ItemDeleteView, ItemUpdateView
from .mysql_views import ProductDataView  # Import the ProductDataView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('register/', RegisterView.as_view()),
    path('login/', LoginView.as_view()),
    path('items/', ItemCreateView.as_view(), name='item-create'),
    path('items/group/', ItemListByGroupView.as_view(), name='item-list-by-group'),
    path('items/<int:item_id>/delete/', ItemDeleteView.as_view(), name='item-delete'),
    path('items/<int:item_id>/update/', ItemUpdateView.as_view(), name='item-update'),
    path('api/product/<str:barcode>/', ProductDataView.as_view(), name='product-data'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
