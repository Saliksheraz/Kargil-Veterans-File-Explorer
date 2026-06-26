from django.shortcuts import render, redirect
from adm.models import Folders, Files
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required

@login_required
def index(request):
    folders = Folders.objects.filter(parent_folder__isnull=True)
    files = Files.objects.filter(folder__isnull=True)
    return render(request, "adm/index.html", {"folders": folders, "files": files})

@login_required
def folder_view(request, pk):
    folder = Folders.objects.get(id=pk)
    sub_folders = Folders.objects.filter(parent_folder=folder)
    files = Files.objects.filter(folder=folder)
    
    breadcrumbs = []
    curr = folder
    while curr is not None:
        breadcrumbs.insert(0, curr)
        curr = curr.parent_folder
        
    return render(request, "adm/folder_view.html", {
        "sub_folders": sub_folders, 
        "files": files, 
        "folder": folder,
        "breadcrumbs": breadcrumbs
    })

@login_required
def create_folder(request):
    if request.method == "POST":
        name = request.POST.get("name")
        parent_id = request.POST.get("parent_folder_id")
        
        parent_folder = None
        if parent_id and parent_id.strip():
            try:
                parent_folder = Folders.objects.get(id=parent_id)
            except Folders.DoesNotExist:
                parent_folder = None
                
        Folders.objects.create(name=name, parent_folder=parent_folder)
        
        if parent_folder:
            return redirect(f"/folder/{parent_folder.id}/")
        return redirect("/")
    return redirect("/")

@login_required
def upload_file(request):
    if request.method == "POST" and request.FILES.get("file"):
        file_obj = request.FILES.get("file")
        folder_id = request.POST.get("folder_id")
        
        folder = None
        if folder_id and folder_id.strip():
            try:
                folder = Folders.objects.get(id=folder_id)
            except Folders.DoesNotExist:
                folder = None
                
        Files.objects.create(file=file_obj, folder=folder)
        
        if folder:
            return redirect(f"/folder/{folder.id}/")
        return redirect("/")
    return redirect("/")

@login_required
def delete_folder(request, pk):
    if request.method == "POST":
        try:
            folder = Folders.objects.get(id=pk)
            parent = folder.parent_folder
            folder.delete()
            if parent:
                return redirect(f"/folder/{parent.id}/")
            return redirect("/")
        except Folders.DoesNotExist:
            pass
    return redirect("/")

@login_required
def delete_file(request, pk):
    if request.method == "POST":
        try:
            file_inst = Files.objects.get(id=pk)
            folder = file_inst.folder
            if file_inst.file:
                file_inst.file.delete(save=False)
            file_inst.delete()
            if folder:
                return redirect(f"/folder/{folder.id}/")
            return redirect("/")
        except Files.DoesNotExist:
            pass
    return redirect("/")
