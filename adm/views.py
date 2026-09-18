import mimetypes
import os
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse, FileResponse, Http404
from django.contrib.auth.decorators import login_required
from adm.models import Folders, Files

from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST
from django.db import transaction
import json

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
import zipfile
import tempfile
import shutil
import re
import xml.etree.ElementTree as ET
from urllib.parse import unquote

def find_libreoffice():
    candidates = [
        r'C:\Program Files\LibreOffice\program\soffice.exe',
        r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
        '/usr/bin/soffice',
        '/usr/local/bin/soffice',
        '/usr/bin/libreoffice',
        '/usr/local/bin/libreoffice',
        '/Applications/LibreOffice.app/Contents/MacOS/soffice',
        'soffice',
        'libreoffice'
    ]
    for c in candidates:
        if os.path.isabs(c) and os.path.exists(c):
            return c
        elif shutil.which(c):
            return shutil.which(c)
    return None

def get_pptx_animation_map(pptx_path):
    """
    Inspects pptx_path to determine if any slide has animations/steppers,
    and returns (has_animations, orig_to_new_map, slide_steps, slide_targets).
    """
    P_NS = 'http://schemas.openxmlformats.org/presentationml/2006/main'
    R_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    REL_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'

    try:
        with zipfile.ZipFile(pptx_path, 'r') as z:
            p_root = ET.fromstring(z.read('ppt/presentation.xml'))
            sldIdLst = p_root.find(f'{{{P_NS}}}sldIdLst')
            if sldIdLst is None or len(sldIdLst) == 0:
                return False, {}, {}, []

            r_root = ET.fromstring(z.read('ppt/_rels/presentation.xml.rels'))
            rel_map = {}
            for rel in r_root.findall(f'{{{REL_NS}}}Relationship'):
                rel_map[rel.attrib['Id']] = rel.attrib['Target']

            slide_targets = []
            for sldId in sldIdLst:
                rId = sldId.attrib.get(f'{{{R_NS}}}id')
                target = rel_map.get(rId)
                if target:
                    if not target.startswith('ppt/'):
                        target = 'ppt/' + target.lstrip('/')
                    slide_targets.append(target)

            has_any_anim = False
            slide_steps = {}
            for target in slide_targets:
                if target not in z.namelist():
                    continue
                s_root = ET.fromstring(z.read(target))
                timing = s_root.find(f'{{{P_NS}}}timing')
                if timing is not None:
                    seq = timing.find(f'.//{{{P_NS}}}seq')
                    if seq is not None:
                        cTn = seq.find(f'{{{P_NS}}}cTn')
                        if cTn is not None:
                            childTnLst = cTn.find(f'{{{P_NS}}}childTnLst')
                            if childTnLst is not None and len(childTnLst) > 0:
                                entr_shapes = set()
                                steps_actions = []
                                for step_par in childTnLst:
                                    actions = []
                                    for node in step_par.iter():
                                        p_class = node.attrib.get('presetClass')
                                        if p_class in ('entr', 'exit'):
                                            targets = [sptgt.attrib.get('spid') for sptgt in node.findall(f'.//{{{P_NS}}}spTgt') if sptgt.attrib.get('spid')]
                                            for t in targets:
                                                if p_class == 'entr':
                                                    entr_shapes.add(t)
                                                actions.append((p_class, t))
                                    if actions:
                                        steps_actions.append(actions)

                                if steps_actions:
                                    has_any_anim = True
                                    current_hidden = set(entr_shapes)
                                    states = [set(current_hidden)]
                                    for actions in steps_actions:
                                        for p_class, spid in actions:
                                            if p_class == 'entr':
                                                current_hidden.discard(spid)
                                            elif p_class == 'exit':
                                                current_hidden.add(spid)
                                        states.append(set(current_hidden))
                                    slide_steps[target] = states

            if not has_any_anim:
                return False, {}, {}, slide_targets

            new_frame_idx = 1
            orig_to_new_map = {}
            for orig_idx, target in enumerate(slide_targets, start=1):
                orig_to_new_map[orig_idx] = new_frame_idx
                states = slide_steps.get(target, [set()])
                new_frame_idx += len(states)

            return True, orig_to_new_map, slide_steps, slide_targets
    except Exception:
        return False, {}, {}, []

def expand_pptx_animations(pptx_path, temp_out_path):
    """
    Detects if pptx_path has slide animations/steppers (clickEffect / build sequences).
    If so, creates an expanded PPTX at temp_out_path where animated slides
    are expanded into multiple static frames (one per animation step).
    Returns (has_animations, orig_to_new_map).
    """
    has_any_anim, orig_to_new_map, slide_steps, slide_targets = get_pptx_animation_map(pptx_path)
    if not has_any_anim:
        return False, {}

    P_NS = 'http://schemas.openxmlformats.org/presentationml/2006/main'
    R_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    A_NS = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    CT_NS = 'http://schemas.openxmlformats.org/package/2006/content-types'
    REL_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'

    ET.register_namespace('p', P_NS)
    ET.register_namespace('r', R_NS)
    ET.register_namespace('a', A_NS)
    ET.register_namespace('', CT_NS)
    ET.register_namespace('', REL_NS)

    try:
        with zipfile.ZipFile(pptx_path, 'r') as z:
            p_root = ET.fromstring(z.read('ppt/presentation.xml'))
            sldIdLst = p_root.find(f'{{{P_NS}}}sldIdLst')
            r_root = ET.fromstring(z.read('ppt/_rels/presentation.xml.rels'))

            temp_dir = tempfile.mkdtemp()
            try:
                z.extractall(temp_dir)

                for ext in list(p_root.findall(f'{{{P_NS}}}extLst')):
                    p_root.remove(ext)
                sldIdLst.clear()

                for rel in list(r_root.findall(f'{{{REL_NS}}}Relationship')):
                    if 'slide' in rel.attrib.get('Type', '') and not 'slideMaster' in rel.attrib.get('Type', '') and not 'notesMaster' in rel.attrib.get('Type', ''):
                        r_root.remove(rel)

                ct_root = ET.fromstring(z.read('[Content_Types].xml'))
                for ov in list(ct_root.findall(f'{{{CT_NS}}}Override')):
                    if '/ppt/slides/slide' in ov.attrib.get('PartName', ''):
                        ct_root.remove(ov)

                def strip_shapes_from_slide(tree_root, hidden_spids):
                    for t in list(tree_root.findall(f'{{{P_NS}}}timing')):
                        tree_root.remove(t)
                    spTree = tree_root.find(f'.//{{{P_NS}}}spTree')
                    if spTree is not None and hidden_spids:
                        for child in list(spTree):
                            cnvpr = child.find(f'.//{{{P_NS}}}cNvPr')
                            if cnvpr is None:
                                cnvpr = child.find(f'.//{{{A_NS}}}cNvPr')
                            if cnvpr is not None and cnvpr.attrib.get('id') in hidden_spids:
                                spTree.remove(child)

                new_frame_idx = 1
                orig_to_new_map = {}

                for orig_idx, target in enumerate(slide_targets, start=1):
                    orig_to_new_map[orig_idx] = new_frame_idx
                    slide_bytes = z.read(target)
                    rels_target = target.replace('ppt/slides/', 'ppt/slides/_rels/') + '.rels'
                    rels_bytes = z.read(rels_target) if rels_target in z.namelist() else None

                    states = slide_steps.get(target, [set()])
                    for hidden in states:
                        s_name = f'slide{new_frame_idx}.xml'
                        s_path = os.path.join(temp_dir, f'ppt/slides/{s_name}')
                        r_name = f'{s_name}.rels'
                        r_path = os.path.join(temp_dir, f'ppt/slides/_rels/{r_name}')

                        s_tree_root = ET.fromstring(slide_bytes)
                        strip_shapes_from_slide(s_tree_root, hidden)
                        with open(s_path, 'wb') as f:
                            f.write(ET.tostring(s_tree_root, encoding='utf-8', xml_declaration=True))

                        if rels_bytes:
                            with open(r_path, 'wb') as f:
                                f.write(rels_bytes)

                        sldId = ET.SubElement(sldIdLst, f'{{{P_NS}}}sldId')
                        sldId.set('id', str(300 + new_frame_idx))
                        sldId.set(f'{{{R_NS}}}id', f'rIdSlide{new_frame_idx}')

                        rel = ET.SubElement(r_root, f'{{{REL_NS}}}Relationship')
                        rel.set('Id', f'rIdSlide{new_frame_idx}')
                        rel.set('Type', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide')
                        rel.set('Target', f'slides/{s_name}')

                        ov = ET.SubElement(ct_root, f'{{{CT_NS}}}Override')
                        ov.set('PartName', f'/ppt/slides/{s_name}')
                        ov.set('ContentType', 'application/vnd.openxmlformats-officedocument.presentationml.slide+xml')

                        new_frame_idx += 1

                with open(os.path.join(temp_dir, 'ppt/presentation.xml'), 'wb') as f:
                    f.write(ET.tostring(p_root, encoding='utf-8', xml_declaration=True))
                with open(os.path.join(temp_dir, 'ppt/_rels/presentation.xml.rels'), 'wb') as f:
                    ET.register_namespace('', REL_NS)
                    f.write(ET.tostring(r_root, encoding='utf-8', xml_declaration=True))
                with open(os.path.join(temp_dir, '[Content_Types].xml'), 'wb') as f:
                    ET.register_namespace('', CT_NS)
                    f.write(ET.tostring(ct_root, encoding='utf-8', xml_declaration=True))

                with zipfile.ZipFile(temp_out_path, 'w', zipfile.ZIP_DEFLATED) as z_out:
                    for foldername, subfolders, filenames in os.walk(temp_dir):
                        for filename in filenames:
                            filepath = os.path.join(foldername, filename)
                            arcname = os.path.relpath(filepath, temp_dir)
                            z_out.write(filepath, arcname)

                return True, orig_to_new_map
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        return False, {}

def extract_pptx_links(pptx_path, orig_to_new_map=None):
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

                    # If animations were expanded, map original slide target to new first frame index
                    if slide_target and orig_to_new_map and slide_target in orig_to_new_map:
                        slide_target = orig_to_new_map[slide_target]

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
                target_page_idx = orig_to_new_map.get(i, i) if orig_to_new_map else i
                slide_links_map[target_page_idx] = links
        except Exception:
            pass

    return slide_links_map

def extract_pptx_videos(pptx_path, previews_dir, cache_key, orig_to_new_map=None):
    """
    Extracts embedded and linked videos from a PPTX presentation.
    Extracts embedded video media files into previews_dir, and determines their
    slide numbers and coordinate boundaries (left_pct, top_pct, width_pct, height_pct).
    Returns a dictionary mapping slide number (1-indexed) to a list of video objects.
    """
    if not os.path.exists(pptx_path) or not pptx_path.lower().endswith('.pptx'):
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

    video_exts = ('.mp4', '.m4v', '.webm', '.ogv', '.mov', '.avi', '.wmv', '.mkv', '.mpg', '.mpeg', '.3gp')
    slide_videos_map = {}

    for i in range(1, 300):
        xml_name = f'ppt/slides/slide{i}.xml'
        if xml_name not in z.namelist():
            break
        rels_name = f'ppt/slides/_rels/slide{i}.xml.rels'
        video_rels = {}
        if rels_name in z.namelist():
            try:
                rels_tree = ET.fromstring(z.read(rels_name))
                for r in rels_tree:
                    r_id = r.attrib.get('Id', '')
                    target = r.attrib.get('Target', '')
                    r_type = r.attrib.get('Type', '').lower()
                    if ('video' in r_type or 'media' in r_type) or target.lower().endswith(video_exts):
                        video_rels[r_id] = target
            except Exception:
                pass

        if not video_rels:
            continue

        try:
            slide_tree = ET.fromstring(z.read(xml_name))
            found_shapes = []

            def process_candidate_shape(elem):
                matched_targets = []
                for vf in elem.iter():
                    tag_local = vf.tag.split('}').pop()
                    if tag_local in ('videoFile', 'media', 'quickTimeFile'):
                        for attr_name, attr_val in vf.attrib.items():
                            if attr_val in video_rels and video_rels[attr_val] not in matched_targets:
                                matched_targets.append(video_rels[attr_val])
                    for attr_name, attr_val in vf.attrib.items():
                        if attr_name.endswith('id') or attr_name.endswith('link') or attr_name.endswith('embed'):
                            if attr_val in video_rels and video_rels[attr_val] not in matched_targets:
                                matched_targets.append(video_rels[attr_val])

                if matched_targets:
                    xfrm = elem.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}xfrm')
                    off_x, off_y, ext_cx, ext_cy = 0, 0, cx, cy
                    has_coords = False
                    if xfrm is not None:
                        off = xfrm.find('{http://schemas.openxmlformats.org/drawingml/2006/main}off')
                        ext = xfrm.find('{http://schemas.openxmlformats.org/drawingml/2006/main}ext')
                        if off is not None and ext is not None and 'x' in off.attrib and 'cx' in ext.attrib:
                            off_x = int(off.attrib['x'])
                            off_y = int(off.attrib['y'])
                            ext_cx = int(ext.attrib['cx'])
                            ext_cy = int(ext.attrib['cy'])
                            has_coords = True

                    for tgt in matched_targets:
                        found_shapes.append({
                            'target': tgt,
                            'off_x': off_x,
                            'off_y': off_y,
                            'ext_cx': ext_cx,
                            'ext_cy': ext_cy,
                            'has_coords': has_coords
                        })

            for pic in slide_tree.iter('{http://schemas.openxmlformats.org/presentationml/2006/main}pic'):
                process_candidate_shape(pic)
            for sp in slide_tree.iter('{http://schemas.openxmlformats.org/presentationml/2006/main}sp'):
                process_candidate_shape(sp)
            for gf in slide_tree.iter('{http://schemas.openxmlformats.org/presentationml/2006/main}graphicFrame'):
                process_candidate_shape(gf)

            if not found_shapes:
                for r_id, tgt in video_rels.items():
                    found_shapes.append({
                        'target': tgt,
                        'off_x': int(cx * 0.1),
                        'off_y': int(cy * 0.1),
                        'ext_cx': int(cx * 0.8),
                        'ext_cy': int(cy * 0.8),
                        'has_coords': True
                    })

            slide_videos = []
            for shape in found_shapes:
                tgt = shape['target']
                video_url = None

                if tgt.startswith('http://') or tgt.startswith('https://'):
                    video_url = tgt
                else:
                    norm_target = tgt.replace('../', 'ppt/').lstrip('/')
                    if not norm_target.startswith('ppt/'):
                        norm_target = 'ppt/' + norm_target

                    if norm_target in z.namelist():
                        clean_fname = f"video_{cache_key}_{os.path.basename(norm_target)}"
                        dest_file = os.path.join(previews_dir, clean_fname)
                        if not os.path.exists(dest_file):
                            try:
                                with open(dest_file, 'wb') as out_f:
                                    out_f.write(z.read(norm_target))
                            except Exception as e:
                                print(f"Error extracting video from pptx: {e}")

                        if os.path.exists(dest_file):
                            video_url = f"{settings.MEDIA_URL}previews/{clean_fname}"

                if video_url:
                    left_pct = round((shape['off_x'] / cx) * 100, 3)
                    top_pct = round((shape['off_y'] / cy) * 100, 3)
                    width_pct = round((shape['ext_cx'] / cx) * 100, 3)
                    height_pct = round((shape['ext_cy'] / cy) * 100, 3)

                    width_pct = max(10, min(100, width_pct))
                    height_pct = max(10, min(100, height_pct))
                    left_pct = max(0, min(100 - width_pct, left_pct))
                    top_pct = max(0, min(100 - height_pct, top_pct))

                    slide_videos.append({
                        'url': video_url,
                        'left_pct': left_pct,
                        'top_pct': top_pct,
                        'width_pct': width_pct,
                        'height_pct': height_pct,
                        'name': os.path.basename(tgt)
                    })

            if slide_videos:
                target_page_idx = orig_to_new_map.get(i, i) if orig_to_new_map else i
                slide_videos_map[target_page_idx] = slide_videos

        except Exception as e:
            print(f"Error processing slide {i} videos: {e}")

    return slide_videos_map

@login_required
def pptx_to_pdf(request):
    """
    On-demand high-fidelity converter:
    Converts a PPTX / PPT file on the server into a native PDF using LibreOffice,
    supporting slide animation steps/steppers by expanding animated slides into
    sequential static frames. Caches the result in media/previews/, extracts interactive hyperlinks,
    extracts embedded/linked slide videos, and returns the response.
    """
    file_url = request.GET.get('url', '')
    if not file_url:
        return JsonResponse({'error': 'No file URL provided'}, status=400)

    clean_url = unquote(file_url).split('?')[0]
    rel_path = clean_url
    if rel_path.startswith('/'):
        rel_path = rel_path[1:]
    if rel_path.startswith('media/'):
        rel_path = rel_path[len('media/'):]

    source_path = os.path.join(settings.MEDIA_ROOT, rel_path)
    if not os.path.exists(source_path):
        return JsonResponse({'error': 'Source file does not exist'}, status=404)

    # Determine unique cache name based on file path and modification time
    mtime = os.path.getmtime(source_path)
    cache_key = hashlib.md5(f"{source_path}_{mtime}".encode('utf-8')).hexdigest()
    previews_dir = os.path.join(settings.MEDIA_ROOT, 'previews')
    os.makedirs(previews_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(source_path))[0]
    cached_pdf_name = f"{base_name}_{cache_key}.pdf"
    cached_pdf_path = os.path.join(previews_dir, cached_pdf_name)
    cached_pdf_url = f"{settings.MEDIA_URL}previews/{cached_pdf_name}"

    # Check if cached PDF already exists
    if os.path.exists(cached_pdf_path) and os.path.getsize(cached_pdf_path) > 0:
        orig_to_new_map = None
        if source_path.lower().endswith('.pptx'):
            _, orig_to_new_map, _, _ = get_pptx_animation_map(source_path)
        slide_links = extract_pptx_links(source_path, orig_to_new_map)
        slide_videos = extract_pptx_videos(source_path, previews_dir, cache_key, orig_to_new_map)
        return JsonResponse({
            'success': True,
            'pdf_url': cached_pdf_url,
            'cached': True,
            'links': slide_links,
            'videos': slide_videos,
            'source_url': file_url
        })

    soffice_exe = find_libreoffice()
    if not soffice_exe:
        return JsonResponse({
            'error': 'LibreOffice engine is not installed on the system.',
            'error_code': 'libreoffice_not_installed',
            'install_instructions': {
                'windows': [
                    'Download LibreOffice from the official website: https://www.libreoffice.org/download/download-libreoffice/',
                    'Run the installer (.msi file) and complete the standard installation (installed to C:\\Program Files\\LibreOffice).',
                    'Restart your terminal/server and try previewing again.'
                ],
                'linux': [
                    'Ubuntu/Debian: sudo apt update && sudo apt install libreoffice -y',
                    'Fedora/RHEL: sudo dnf install libreoffice -y'
                ],
                'macos': [
                    'Homebrew: brew install --cask libreoffice'
                ]
            }
        }, status=501)

    temp_expanded_pptx = None
    input_to_convert = source_path
    orig_to_new_map = None

    # Check if PPTX contains animation steps to expand
    if source_path.lower().endswith('.pptx'):
        expanded_candidate = os.path.join(previews_dir, f"{base_name}_{cache_key}_expanded.pptx")
        has_anim, sld_map = expand_pptx_animations(source_path, expanded_candidate)
        if has_anim and os.path.exists(expanded_candidate):
            input_to_convert = expanded_candidate
            temp_expanded_pptx = expanded_candidate
            orig_to_new_map = sld_map

    # Extract interactive hyperlinks from PPTX (with slide mapping if animated)
    slide_links = extract_pptx_links(source_path, orig_to_new_map)

    try:
        # Convert directly to previews dir
        cmd = [soffice_exe, '--headless', '--convert-to', 'pdf', input_to_convert, '--outdir', previews_dir]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        # Determine expected output filename from LibreOffice
        input_basename = os.path.splitext(os.path.basename(input_to_convert))[0]
        default_out_pdf = os.path.join(previews_dir, f"{input_basename}.pdf")

        if os.path.exists(default_out_pdf):
            if os.path.exists(cached_pdf_path):
                os.remove(cached_pdf_path)
            os.rename(default_out_pdf, cached_pdf_path)

            slide_videos = extract_pptx_videos(source_path, previews_dir, cache_key, orig_to_new_map)
            return JsonResponse({
                'success': True,
                'pdf_url': cached_pdf_url,
                'cached': False,
                'links': slide_links,
                'videos': slide_videos,
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
    finally:
        if temp_expanded_pptx and os.path.exists(temp_expanded_pptx):
            try:
                os.remove(temp_expanded_pptx)
            except Exception:
                pass

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
            
            remove_image = request.POST.get("remove_image") in ("true", "1", "on")
            if remove_image:
                if folder.image:
                    try:
                        folder.image.delete(save=False)
                    except Exception:
                        pass
                    folder.image = None
                if folder.thumbnail:
                    try:
                        folder.thumbnail.delete(save=False)
                    except Exception:
                        pass
                    folder.thumbnail = None
            else:
                image_obj = request.FILES.get("image")
                if image_obj:
                    folder.image = image_obj
            
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

@login_required
@require_POST
def reorder_items(request):
    """
    Persists drag-and-drop arrangement of files and folders.
    Accepts JSON: { "items": [ {"type": "folder"|"file", "id": 1, "order": 0}, ... ] }
    """
    try:
        data = json.loads(request.body)
        items = data.get('items', [])
        with transaction.atomic():
            for item in items:
                item_type = item.get('type')
                item_id = item.get('id')
                item_order = int(item.get('order', 0))
                if item_type == 'folder':
                    Folders.objects.filter(id=item_id).update(order=item_order)
                elif item_type == 'file':
                    Files.objects.filter(id=item_id).update(order=item_order)
        return JsonResponse({'status': 'success', 'updated_count': len(items)})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

