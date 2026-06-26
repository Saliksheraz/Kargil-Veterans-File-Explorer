"""
URL configuration for dashboard project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""


from django.contrib import admin
from django.urls import path, include
from adm.views import index, folder_view, create_folder, upload_file, delete_folder, delete_file
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('users.urls')),
    path('', index),
    path('folder/<int:pk>/', folder_view),
    path('create-folder/', create_folder, name='create_folder'),
    path('upload-file/', upload_file, name='upload_file'),
    path('delete-folder/<int:pk>/', delete_folder, name='delete_folder'),
    path('delete-file/<int:pk>/', delete_file, name='delete_file'),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
