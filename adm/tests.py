import os
import hashlib
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from django.test import TestCase, Client
from django.test import SimpleTestCase, RequestFactory, override_settings
from django.contrib.auth.models import User
from django.conf import settings
from adm.models import Folders, Files

class LocalAssetsAnd360VideoTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.folder = Folders.objects.create(name="Orientation Materials")

    def test_local_vendor_assets_exist(self):
        """Ensure all external vendor assets are locally hosted in static/."""
        vendor_dir = os.path.join(settings.BASE_DIR, 'static', 'vendor')
        expected_files = [
            os.path.join(vendor_dir, 'three', 'three.min.js'),
            os.path.join(vendor_dir, 'jquery', 'jquery-3.7.1.min.js'),
            os.path.join(vendor_dir, 'bootstrap', 'css', 'bootstrap.min.css'),
            os.path.join(vendor_dir, 'bootstrap', 'js', 'bootstrap.bundle.min.js'),
            os.path.join(vendor_dir, 'bootstrap-icons', 'bootstrap-icons.css'),
            os.path.join(vendor_dir, 'bootstrap-icons', 'fonts', 'bootstrap-icons.woff2'),
            os.path.join(vendor_dir, 'mammoth', 'mammoth.browser.min.js'),
            os.path.join(vendor_dir, 'xlsx', 'xlsx.full.min.js'),
            os.path.join(vendor_dir, 'jszip', 'jszip.min.js'),
            os.path.join(vendor_dir, 'pdfjs', 'pdf.min.js'),
            os.path.join(vendor_dir, 'pdfjs', 'pdf.worker.min.js'),
        ]
        for fpath in expected_files:
            self.assertTrue(os.path.exists(fpath), f"Missing local static file: {fpath}")
            self.assertGreater(os.path.getsize(fpath), 0, f"File is empty: {fpath}")

    def test_video360_player_assets_exist(self):
        """Ensure 360 video player JS and CSS exist in static/."""
        js_path = os.path.join(settings.BASE_DIR, 'static', 'js', 'video360_player.js')
        css_path = os.path.join(settings.BASE_DIR, 'static', 'css', 'video360_player.css')

        self.assertTrue(os.path.exists(js_path), "Missing static/js/video360_player.js")
        self.assertTrue(os.path.exists(css_path), "Missing static/css/video360_player.css")
        self.assertGreater(os.path.getsize(js_path), 0)
        self.assertGreater(os.path.getsize(css_path), 0)

    def test_image360_viewer_assets_exist(self):
        """Ensure 360 image viewer JS and CSS exist in static/."""
        js_path = os.path.join(settings.BASE_DIR, 'static', 'js', 'image360_viewer.js')
        css_path = os.path.join(settings.BASE_DIR, 'static', 'css', 'image360_viewer.css')

        self.assertTrue(os.path.exists(js_path), "Missing static/js/image360_viewer.js")
        self.assertTrue(os.path.exists(css_path), "Missing static/css/image360_viewer.css")
        self.assertGreater(os.path.getsize(js_path), 0)
        self.assertGreater(os.path.getsize(css_path), 0)

    def test_doc_viewer_loads_360_player_and_local_assets(self):
        """Verify doc_viewer renders 360 video and image containers and local static links."""
        self.client.login(username='testuser', password='password123')
        response = self.client.get('/view-doc/', {'url': '/media/files/kargil_memorial_360.mp4', 'name': 'kargil_memorial_360.mp4'})
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        # Check local assets
        self.assertIn('/static/vendor/three/three.min.js', content)
        self.assertIn('/static/js/video360_player.js', content)
        self.assertIn('/static/css/video360_player.css', content)
        self.assertIn('/static/js/image360_viewer.js', content)
        self.assertIn('/static/css/image360_viewer.css', content)
        self.assertIn('/static/vendor/bootstrap/css/bootstrap.min.css', content)
        self.assertIn('docViewerVideoContainer', content)
        self.assertIn('docViewerImageContainer', content)

        # Ensure NO external CDN references exist
        self.assertNotIn('https://cdn.jsdelivr.net', content)

        self.assertNotIn('https://cdnjs.cloudflare.com', content)
        self.assertNotIn('https://code.jquery.com', content)

    def test_base_template_loads_360_and_local_assets(self):
        """Verify index dashboard renders local static files and 360 video/image components."""
        self.client.login(username='testuser', password='password123')
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        self.assertIn('/static/vendor/three/three.min.js', content)
        self.assertIn('/static/js/video360_player.js', content)
        self.assertIn('/static/css/video360_player.css', content)
        self.assertIn('/static/js/image360_viewer.js', content)
        self.assertIn('/static/css/image360_viewer.css', content)
        self.assertIn('modalVideoPlayerContainer', content)
        self.assertIn('modalImageViewerContainer', content)
        self.assertIn('is360ImageName', content)
        self.assertIn('badge-360-photo', content)

        # Ensure NO external CDN references exist
        self.assertNotIn('https://cdn.jsdelivr.net', content)
        self.assertNotIn('https://cdnjs.cloudflare.com', content)
        self.assertNotIn('https://code.jquery.com', content)

    def test_folder_view_renders_360_support(self):
        """Verify folder_view renders 360 video and image badge logic and local assets."""
        self.client.login(username='testuser', password='password123')
        response = self.client.get(f'/folder/{self.folder.id}/')
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        self.assertIn('is360VideoName', content)
        self.assertIn('is360ImageName', content)
        self.assertIn('badge-360-video', content)
        self.assertIn('badge-360-photo', content)
        self.assertNotIn('https://cdn.jsdelivr.net', content)


class EmbeddedPowerPointVideoTest(SimpleTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / 'orientation.pptx'
        self.previews = Path(self.temp.name) / 'previews'
        self.previews.mkdir()
        with zipfile.ZipFile(self.source, 'w') as deck:
            deck.writestr('ppt/presentation.xml', '''<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:sldSz cx="1000" cy="1000"/></p:presentation>''')
            deck.writestr('ppt/slides/slide1.xml', '''<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main"><p:cSld><p:spTree><p:pic><p:nvPicPr><p:cNvPr id="2" name="Hilltop 360 panorama" descr="Drag to look around"/><p:nvPr><a:videoFile r:link="rId1"/><p14:media r:embed="rId2"/></p:nvPr></p:nvPicPr><p:spPr><a:xfrm rot="5400000"><a:off x="100" y="200"/><a:ext cx="500" cy="400"/></a:xfrm></p:spPr></p:pic></p:spTree></p:cSld></p:sld>''')
            deck.writestr('ppt/slides/_rels/slide1.xml.rels', '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/video" Target="../media/media1.mp4"/><Relationship Id="rId2" Type="http://schemas.microsoft.com/office/2007/relationships/media" Target="../media/media1.mp4"/></Relationships>''')
            deck.writestr('ppt/media/media1.mp4', b'embedded video fixture')

    def test_extraction_keeps_360_shape_title_and_geometry_without_duplicate_video(self):
        from adm.views import extract_pptx_videos
        videos = extract_pptx_videos(str(self.source), str(self.previews), 'test', {1: 3})
        self.assertEqual(list(videos), [3])
        self.assertEqual(len(videos[3]), 1)
        clip = videos[3][0]
        self.assertEqual(clip['name'], 'media1.mp4')
        self.assertIn('360 panorama', clip['title'])
        self.assertEqual([clip[k] for k in ('left_pct', 'top_pct', 'width_pct', 'height_pct', 'rotation')], [10, 20, 50, 40, 90])
        self.assertEqual((self.previews / 'video_test_media1.mp4').read_bytes(), b'embedded video fixture')

    def test_cached_pdf_still_returns_embedded_video_metadata(self):
        from adm.views import pptx_to_pdf
        key = hashlib.md5(f'{self.source}_{self.source.stat().st_mtime}'.encode()).hexdigest()
        (self.previews / f'orientation_{key}.pdf').write_bytes(b'cached PDF')
        request = RequestFactory().get('/pptx-to-pdf/', {'url': '/media/orientation.pptx'})
        request.user = SimpleNamespace(is_authenticated=True)
        with override_settings(MEDIA_ROOT=self.temp.name):
            response = pptx_to_pdf(request)
        import json
        payload = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['cached'])
        self.assertIn('360 panorama', payload['videos']['1'][0]['title'])

    def test_legacy_ppt_is_normalized_once_for_media_extraction(self):
        from adm.views import prepare_presentation_source, extract_pptx_videos
        source = Path(self.temp.name) / 'legacy.ppt'
        source.write_bytes(b'binary PPT fixture')

        def convert(command, **kwargs):
            converted = Path(command[-1]) / 'legacy.pptx'
            converted.write_bytes(self.source.read_bytes())
            return SimpleNamespace(stdout='', stderr='', returncode=0)

        with patch('adm.views.find_libreoffice', return_value='soffice'), patch('adm.views.subprocess.run', side_effect=convert) as run:
            normalized = prepare_presentation_source(str(source), str(self.previews), 'legacy')
            self.assertEqual(prepare_presentation_source(str(source), str(self.previews), 'legacy'), normalized)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][3], 'pptx')
            self.assertEqual(len(extract_pptx_videos(normalized, str(self.previews), 'legacy')[1]), 1)
