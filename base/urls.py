from django.urls import path

from . import views

# aplicando namespacing: todas as urls pertencem a base/
app_name = 'base'

urlpatterns = [
    path('', views.index, name='index'),
]
