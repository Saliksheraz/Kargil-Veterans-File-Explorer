import mimetypes
import os
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse, FileResponse, Http404
from django.contrib.auth.decorators import login_required
from adm.models import Folders, Files

from django.views.decorators.clickjacking import xframe_options_sameorigin

@login_required
@xframe_options_sameorigin
def serve_media(request, path):
    file_path = os.path.join(settings.MEDIA_ROOT, path)
    if not os.path.exists(file_path) or os.path.isdir(file_path):
        raise Http404("File not found")
        
    content_type, _ = mimetypes.guess_type(file_path)
    if not content_type:
        content_type = 'application/octet-stream'
        
    response = FileResponse(open(file_path, 'rb'), content_type=content_type)
    file_name = os.path.basename(file_path)
    
    # Inline disposition forces browser to display file in browser instead of downloading
    response['Content-Disposition'] = f'inline; filename="{file_name}"'
    response['X-Frame-Options'] = 'SAMEORIGIN'
    return response

from urllib.parse import unquote

@login_required
@xframe_options_sameorigin
def doc_viewer(request):
    file_url = request.GET.get('url', '')
    file_name = request.GET.get('name', '')
    if file_url:
        file_url = unquote(file_url)
    if not file_name and file_url:
        file_name = os.path.basename(file_url)
    if file_name:
        file_name = unquote(file_name)
    clean_name = file_name.replace('uploads/', '').replace('files/', '')
    return render(request, "adm/doc_viewer.html", {
        "file_url": file_url,
        "file_name": clean_name
    })

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
        
    custom_bg = folder.image.url if folder.image else None

    return render(request, "adm/folder_view.html", {
        "sub_folders": sub_folders, 
        "files": files, 
        "folder": folder,
        "breadcrumbs": breadcrumbs,
        "custom_bg": custom_bg
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
                
        image_obj = request.FILES.get("image")
        Folders.objects.create(name=name, parent_folder=parent_folder, image=image_obj)
        
        if parent_folder:
            return redirect(f"/folder/{parent_folder.id}/")
        return redirect("/")
    return redirect("/")

@login_required
def upload_file(request):
    if request.method == "POST":
        file_list = request.FILES.getlist("files") or request.FILES.getlist("file")
        folder_id = request.POST.get("folder_id")
        
        folder = None
        if folder_id and folder_id.strip():
            try:
                folder = Folders.objects.get(id=folder_id)
            except Folders.DoesNotExist:
                folder = None
                
        created_count = 0
        for f in file_list:
            Files.objects.create(file=f, folder=folder)
            created_count += 1
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', ''):
            redirect_url = f"/folder/{folder.id}/" if folder else "/"
            return JsonResponse({"status": "success", "count": created_count, "redirect_url": redirect_url})
            
        if folder:
            return redirect(f"/folder/{folder.id}/")
        return redirect("/")
    return redirect("/")

@login_required
def update_folder(request, pk):
    if request.method == "POST":
        try:
            folder = Folders.objects.get(id=pk)
            name = request.POST.get("name")
            if name:
                folder.name = name
            
            image_obj = request.FILES.get("image")
            if image_obj:
                folder.image = image_obj
            
            # Optionally clear image if a specific flag is passed, but UI might not have it yet.
            folder.save()
            
            if folder.parent_folder:
                return redirect(f"/folder/{folder.parent_folder.id}/")
            return redirect("/")
        except Folders.DoesNotExist:
            pass
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
