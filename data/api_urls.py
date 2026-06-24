from django.urls import path, include
from rest_framework.routers import DefaultRouter
from data.api_views import (
    cheatersheet_api_proxy,
    import_imgpt_proxy,
)

router = DefaultRouter()
urlpatterns = [
    path('', include(router.urls)),
    path('import-imgpt-data/', import_imgpt_proxy, name='api-import-imgpt'),
    path('cheatersheet/', cheatersheet_api_proxy, name='api-cheatersheet-root'),
    path('cheatersheet/<path:path>', cheatersheet_api_proxy, name='api-cheatersheet-proxy'),
]
