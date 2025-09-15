from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),  # 루트 경로에 index 뷰 연결
    path('api/search_jobs/', views.search_jobs, name='search_jobs'),
    path('api/get_company_info/', views.get_company_info, name='get_company_info'),
    path('api/generate_resume/', views.generate_resume, name='generate_resume'),
]