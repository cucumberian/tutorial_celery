from django.urls import path
from . import views


urlpatterns = [
    path('', views.IndexView.as_view(), name="index"),
    path('add_task/', views.AddTaskView.as_view(), name="add_task"),
]