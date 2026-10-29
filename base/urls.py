from django.urls import path

from . import views

# aplicando namespacing: todas as urls pertencem a base/
app_name = 'base'

urlpatterns = [
    path('', views.index, name='index'),
    path('entrar/', views.login_view, name='login'),
    path('cadastro/', views.register, name='register'),
    path('sair/', views.logout_view, name='logout'),
]
