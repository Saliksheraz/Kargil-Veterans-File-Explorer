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

    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    range_header = request.META.get('HTTP_RANGE', '').strip()

    if range_header and range_header.startswith('bytes='):
        try:
            byte_range = range_header.split('=')[1].split('-')
            start_byte = int(byte_range[0])
            end_byte = int(byte_range[1]) if byte_range[1] else file_size - 1
            if end_byte >= file_size:
                end_byte = file_size - 1

            length = end_byte - start_byte + 1
            with open(file_path, 'rb') as f:
                f.seek(start_byte)
                data = f.read(length)

            response = HttpResponse(data, status=206, content_type=content_type)
            response['Content-Range'] = f'bytes {start_byte}-{end_byte}/{file_size}'
            response['Content-Length'] = str(length)
            response['Accept-Ranges'] = 'bytes'
            response['Content-Disposition'] = f'inline; filename="{file_name}"'
            response['X-Frame-Options'] = 'SAMEORIGIN'
            return response
        except Exception:
            pass

    response = FileResponse(open(file_path, 'rb'), content_type=content_type)
    response['Accept-Ranges'] = 'bytes'
    response['Content-Length'] = str(file_size)
    response['Content-Disposition'] = f'inline; filename="{file_name}"'
    response['X-Frame-Options'] = 'SAMEORIGIN'
    return response

import hashlib
import subprocess
from urllib.parse import unquote

def find_libreoffice():
    candidates = [
        r'C:\Program Files\LibreOffice\program\soffice.exe',
        r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
        'soffice'
    ]
    for c in candidates:
        if os.path.exists(c) or c == 'soffice':
            return c
    return None

def extract_pptx_links(pptx_path):
    import zipfile, re, xml.etree.ElementTree as ET
    if not os.path.exists(pptx_path):
        return {}
    try:
        z = zipfile.ZipFile(pptx_path)
    except Exception:
        return {}

    cx, cy = 12192000, 6858000
    try:
        pres_tree = ET.fromstring(z.read('ppt/presentation.xml'))
        sld_sz = pres_tree.find('.//{http://schemas.openxmlformats.org/presentationml/2006/main}sldSz')
        if sld_sz is not None:
            cx = int(sld_sz.attrib.get('cx', cx))
            cy = int(sld_sz.attrib.get('cy', cy))
    except Exception:
        pass

    slide_links_map = {}
    for i in range(1, 200):
        xml_name = f'ppt/slides/slide{i}.xml'
        if xml_name not in z.namelist():
            break
        rels_name = f'ppt/slides/_rels/slide{i}.xml.rels'
        rels = {}
        if rels_name in z.namelist():
            try:
                rels_tree = ET.fromstring(z.read(rels_name))
                for r in rels_tree:
                    rels[r.attrib['Id']] = r.attrib.get('Target', '')
            except Exception:
                pass

        try:
            slide_tree = ET.fromstring(z.read(xml_name))
            links = []

            def check_element(elem, xfrm_sp=None):
                for hlink in elem.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}hlinkClick'):
                    rId = hlink.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id', '')
                    action = hlink.attrib.get('action', '')
                    target = rels.get(rId, '')
                    slide_target = None
                    url_target = None
                    if target:
                        if 'slide' in target:
                            m = re.search(r'slide(\d+)', target)
                            if m: slide_target = int(m.group(1))
                        elif target.startswith('http'):
                            url_target = target
                    elif 'hlinksldjump' in action:
                        m = re.search(r'slide(\d+)', action)
                        if m: slide_target = int(m.group(1))

                    if not slide_target and not url_target:
                        continue

                    sp_to_search = xfrm_sp if xfrm_sp is not None else elem
                    xfrm = sp_to_search.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}xfrm')
                    if xfrm is not None:
                        off = xfrm.find('{http://schemas.openxmlformats.org/drawingml/2006/main}off')
                        ext = xfrm.find('{http://schemas.openxmlformats.org/drawingml/2006/main}ext')
                        if off is not None and ext is not None and 'x' in off.attrib and 'cx' in ext.attrib:
                            links.append({
                                'left_pct': round((int(off.attrib['x']) / cx) * 100, 3),
                                'top_pct': round((int(off.attrib['y']) / cy) * 100, 3),
                                'width_pct': round((int(ext.attrib['cx']) / cx) * 100, 3),
                                'height_pct': round((int(ext.attrib['cy']) / cy) * 100, 3),
                                'slide_jump': slide_target,
                                'url': url_target
                            })

            for sp in slide_tree.iter('{http://schemas.openxmlformats.org/presentationml/2006/main}sp'):
                check_element(sp, sp)
            for pic in slide_tree.iter('{http://schemas.openxmlformats.org/presentationml/2006/main}pic'):
                check_element(pic, pic)

            if links:
                slide_links_map[i] = links
        except Exception:
            pass

    return slide_links_map

@login_required
def pptx_to_pdf(request):
    """
    On-demand high-fidelity converter:
    Converts a PPTX / PPT file on the server into a native PDF using LibreOffice,
    caches the result in media/previews/, extracts interactive hyperlinks, and returns the response.
    """
    file_url = request.GET.get('url', '')
    if not file_url:
        return JsonResponse({'error': 'No file URL provided'}, status=400)

    clean_url = unquote(file_url).split('?')[0]
    # Remove leading slash or media/ prefix if needed to locate in MEDIA_ROOT
    rel_path = clean_url
    if rel_path.startswith('/'):
        rel_path = rel_path[1:]
    if rel_path.startswith('media/'):
        rel_path = rel_path[len('media/'):]

    source_path = os.path.join(settings.MEDIA_ROOT, rel_path)
    if not os.path.exists(source_path):
        return JsonResponse({'error': 'Source file does not exist'}, status=404)

    # Extract interactive hyperlinks from PPTX
    slide_links = extract_pptx_links(source_path)

    # Determine unique cache name based on file path and modification time
    mtime = os.path.getmtime(source_path)
    cache_key = hashlib.md5(f"{source_path}_{mtime}".encode('utf-8')).hexdigest()
    previews_dir = os.path.join(settings.MEDIA_ROOT, 'previews')
    os.makedirs(previews_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(source_path))[0]
    cached_pdf_name = f"{base_name}_{cache_key}.pdf"
    cached_pdf_path = os.path.join(previews_dir, cached_pdf_name)
    cached_pdf_url = f"{settings.MEDIA_URL}previews/{cached_pdf_name}"

    if os.path.exists(cached_pdf_path) and os.path.getsize(cached_pdf_path) > 0:
        return JsonResponse({
            'success': True,
            'pdf_url': cached_pdf_url,
            'cached': True,
            'links': slide_links,
            'source_url': file_url
        })

    soffice_exe = find_libreoffice()
    if not soffice_exe:
        return JsonResponse({'error': 'LibreOffice engine not installed on server'}, status=501)

    try:
        # Convert directly to previews dir
        cmd = [soffice_exe, '--headless', '--convert-to', 'pdf', source_path, '--outdir', previews_dir]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        default_out_pdf = os.path.join(previews_dir, f"{base_name}.pdf")

        if os.path.exists(default_out_pdf):
            # Rename to cached name with hash
            if os.path.exists(cached_pdf_path):
                os.remove(cached_pdf_path)
            os.rename(default_out_pdf, cached_pdf_path)

            return JsonResponse({
                'success': True,
                'pdf_url': cached_pdf_url,
                'cached': False,
                'links': slide_links,
                'source_url': file_url
            })
        else:
            return JsonResponse({
                'error': 'Conversion failed to generate PDF output',
                'details': result.stderr or result.stdout
            }, status=500)

    except subprocess.TimeoutExpired:
        return JsonResponse({'error': 'Conversion timed out'}, status=504)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

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
