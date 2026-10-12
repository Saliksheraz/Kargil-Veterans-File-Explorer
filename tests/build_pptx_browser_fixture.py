"""Generate temporary media and rendered templates for the browser regression test."""
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import django
django.setup()
from django.template.loader import render_to_string
from django.test import RequestFactory, override_settings
from django.contrib.auth.models import AnonymousUser
from adm.views import extract_pptx_videos

output = Path(sys.argv[1])
for name, size in [('media1', '320x160'), ('media2', '320x180')]:
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'testsrc2=size={size}:rate=10',
                    '-t', '2', '-c:v', 'libvpx', '-y', str(output / f'{name}.webm')], check=True)

pres_ns = 'http://schemas.openxmlformats.org/presentationml/2006/main'
draw_ns = 'http://schemas.openxmlformats.org/drawingml/2006/main'
rel_ns = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'

with zipfile.ZipFile(output / 'fixture.pptx', 'w') as deck:
    deck.writestr('ppt/presentation.xml', f'<p:presentation xmlns:p="{pres_ns}"><p:sldSz cx="1600" cy="900"/></p:presentation>')
    for number in range(1, 4):
        shape = f'''<p:pic><p:nvPicPr><p:cNvPr id="2" name="media{number}.webm"/><p:nvPr><a:videoFile r:link="rId1"/></p:nvPr></p:nvPicPr><p:spPr><a:xfrm><a:off x="200" y="100"/><a:ext cx="1200" cy="650"/></a:xfrm></p:spPr></p:pic>''' if number < 3 else ''
        # The second slide also exercises video overlays on a map/image slide.
        text = ''.join(f'<p:sp><p:spPr><a:xfrm><a:off x="10" y="{10+i*30}"/><a:ext cx="100" cy="20"/></a:xfrm></p:spPr><p:txBody><a:p><a:r><a:t>Label {i}</a:t></a:r></a:p></p:txBody></p:sp>' for i in range(2)) if number == 2 else ''
        deck.writestr(f'ppt/slides/slide{number}.xml', f'<p:sld xmlns:p="{pres_ns}" xmlns:a="{draw_ns}" xmlns:r="{rel_ns}"><p:cSld><p:spTree>{shape}{text}</p:spTree></p:cSld></p:sld>')
        rels = f'<Relationship Id="rId1" Type="{rel_ns}/video" Target="../media/media{number}.webm"/><Relationship Id="rId2" Type="http://schemas.microsoft.com/office/2007/relationships/media" Target="../media/media{number}.webm"/>' if number < 3 else ''
        if number == 2:
            rels += f'<Relationship Id="rId3" Type="{rel_ns}/image" Target="../media/background.png"/>'
        deck.writestr(f'ppt/slides/_rels/slide{number}.xml.rels', f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>')
    for number in (1, 2):
        deck.writestr(f'ppt/media/media{number}.webm', (output / f'media{number}.webm').read_bytes())
    import base64
    deck.writestr('ppt/media/background.png', base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII='))

# Three blank PDF slides, with a real cross-reference table for PDF.js.
objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R 4 0 R 5 0 R] /Count 3 >>']
objects += [b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 800 450] /Resources <<>> >>'] * 3
pdf = b'%PDF-1.4\n'
offsets = [0]
for index, obj in enumerate(objects, 1):
    offsets.append(len(pdf))
    pdf += f'{index} 0 obj\n'.encode() + obj + b'\nendobj\n'
xref = len(pdf)
pdf += f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode()
pdf += b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets[1:])
pdf += f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF'.encode()
(output / 'slides.pdf').write_bytes(pdf)

(output / 'previews').mkdir()
with override_settings(MEDIA_URL='/media/'):
    videos = extract_pptx_videos(str(output / 'fixture.pptx'), str(output / 'previews'), 'browser')
(output / 'response.json').write_text(json.dumps({'success': True, 'pdf_url': '/media/slides.pdf', 'videos': videos, 'links': {}}))
request = RequestFactory().get('/')
request.user = AnonymousUser()
for name, template, context in [
    ('doc.html', 'adm/doc_viewer.html', {'file_url': '/media/fixture.pptx', 'file_name': 'fixture.pptx'}),
    ('video.html', 'adm/doc_viewer.html', {'file_url': '/media/media1.webm', 'file_name': '360.webm'}),
    ('index.html', 'adm/index.html', {'folders': [], 'files': []}),
]:
    (output / name).write_text(render_to_string(template, context, request=request), encoding='utf-8')
