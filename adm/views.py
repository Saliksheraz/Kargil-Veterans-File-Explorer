from django.shortcuts import render
from adm.models import Folders, Files
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required

@login_required
def index(request):
    folders = Folders.objects.filter(parent_folder__isnull=True)
    return render(request, "adm/index.html", {"folders": folders})

@login_required
def folder_view(request, pk):
    folder = Folders.objects.get(id=pk)
    sub_folders = Folders.objects.filter(parent_folder=folder)
    files = Files.objects.filter(folder=folder)
    return render(request, "adm/folder_view.html", {"sub_folders": sub_folders, "files":files, "folder": folder})
