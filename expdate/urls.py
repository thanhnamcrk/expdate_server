"""
URL configuration for expdate project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from accounts.item_views import ItemCreateView
from accounts.mysql_views import ProductDataView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/accounts/', include('accounts.urls')),  # đường dẫn chính cho accounts
    path('accounts/', include('accounts.urls')),
    path('api/items/', ItemCreateView.as_view(), name='item-create'),  # Direct mapping for /api/items/
    path('api/product/<str:barcode>/', ProductDataView.as_view(), name='product-data'),  # Direct mapping for /api/product/<barcode>/
]
