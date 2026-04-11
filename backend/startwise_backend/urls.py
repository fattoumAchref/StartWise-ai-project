from django.urls import include, path


urlpatterns = [
    path("", include("ideation.urls")),
    path("product-audit/", include("product_audit.urls")),
]
