import os
from django.test import TestCase, Client
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
