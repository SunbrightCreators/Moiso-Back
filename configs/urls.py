from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('proposals/', include('proposals.urls')),
    path('pays/', include('pays.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
