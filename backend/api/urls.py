from django.urls import path

from . import views

urlpatterns = [
    path('health/', views.health, name='health'),
    path('analyses/', views.analyse, name='analyse'),
    path('library/', views.library, name='library'),
]
