from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('', include('myapp.urls')),  # /chat/recommend/ 가 여기 포함되어야 함
    path('admin/', admin.site.urls),
]
