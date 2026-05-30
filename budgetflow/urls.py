from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import landing_page

urlpatterns = [
    path('', landing_page, name='landing'),
    path('django-admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('', include('core.urls')),
    # JWT API endpoints
    path('api/', include('accounts.api_urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
