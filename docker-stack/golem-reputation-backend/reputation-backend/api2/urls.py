from django.urls import path
from django.shortcuts import render
from .api import api

app_name = 'api2'

urlpatterns = [
    path("", api.urls),
    ]
