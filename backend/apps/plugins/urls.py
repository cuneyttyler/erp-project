from django.urls import path

from . import views

urlpatterns = [
    path("", views.PluginListView.as_view(), name="plugin-list"),
    # The widget routes come first: "widgets" must not be read as a plugin key.
    path("widgets/", views.WidgetListView.as_view(), name="widget-list"),
    path("widgets/layout/", views.WidgetLayoutView.as_view(), name="widget-layout"),
    path("widgets/layout/reset/", views.WidgetLayoutResetView.as_view(), name="widget-layout-reset"),
    path("widgets/<slug:key>/data/", views.WidgetDataView.as_view(), name="widget-data"),
    path("<slug:key>/", views.PluginDetailView.as_view(), name="plugin-detail"),
]
