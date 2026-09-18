from django.db import models
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
import os

class Folders(models.Model):
    parent_folder = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=200, null=True, blank=True)
    image = models.ImageField(upload_to="folder_images", null=True, blank=True)
    thumbnail = models.ImageField(upload_to="folder_thumbnails", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ['order', 'id']

    def save(self, *args, **kwargs):
        needs_new_thumbnail = False
        old_thumbnail = None

        if self.pk:
            try:
                orig = Folders.objects.filter(pk=self.pk).only('image', 'thumbnail').first()
                if orig:
                    if orig.image != self.image:
                        needs_new_thumbnail = True
                        old_thumbnail = orig.thumbnail
            except Exception:
                pass
        else:
            if self.image:
                needs_new_thumbnail = True

        if self.image and (needs_new_thumbnail or not self.thumbnail):
            try:
                if hasattr(self.image, 'open'):
                    self.image.open()
                img = Image.open(self.image)
                if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                    img = img.convert('RGB')
                img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                thumb_io = BytesIO()
                img.save(thumb_io, format='JPEG', quality=85)

                if old_thumbnail and old_thumbnail.name:
                    try:
                        old_thumbnail.delete(save=False)
                    except Exception:
                        pass

                thumb_name = os.path.basename(self.image.name) if hasattr(self.image, 'name') and self.image.name else 'thumb.jpg'
                base_name, _ = os.path.splitext(thumb_name)
                self.thumbnail.save(f"thumb_{base_name}.jpg", ContentFile(thumb_io.getvalue()), save=False)
            except Exception as e:
                print(f"Error generating thumbnail: {e}")
        elif not self.image:
            if self.thumbnail:
                try:
                    self.thumbnail.delete(save=False)
                except Exception:
                    pass
            self.thumbnail = None
            
        super().save(*args, **kwargs)

    @property
    def file_count(self):
        # Count direct files and files in subfolders recursively
        direct_files = self.files_set.count()
        subfolders_files = sum(sub.file_count for sub in Folders.objects.filter(parent_folder=self))
        return direct_files + subfolders_files

    @property
    def total_size(self):
        total = 0
        for f in self.files_set.all():
            if f.file:
                try:
                    total += f.file.size
                except Exception:
                    pass
        for sub in Folders.objects.filter(parent_folder=self):
            total += sub.total_size
        return total

    @property
    def total_size_formatted(self):
        size = self.total_size
        return self._format_size(size)

    def _format_size(self, size_bytes):
        if size_bytes == 0:
            return "0 B"
        import math
        size_name = ("B", "KB", "MB", "GB", "TB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"

    @property
    def all_files(self):
        # Recursively get all files in this folder and any nested subfolders
        file_list = list(self.files_set.all())
        for sub in Folders.objects.filter(parent_folder=self):
            file_list.extend(sub.all_files)
        return file_list

    @property
    def folder_tree(self):
        """
        Recursively builds a tree dictionary of subfolders and direct files.
        """
        subfolders_data = [sub.folder_tree for sub in Folders.objects.filter(parent_folder=self).order_by('name')]
        files_data = []
        for f in self.files_set.all().order_by('file'):
            if f.file:
                clean_name = os.path.basename(f.file.name)
                files_data.append({
                    'id': f.id,
                    'name': clean_name,
                    'raw_name': f.file.name,
                    'url': f.file.url,
                    'size': f.file_size_formatted
                })
        return {
            'id': self.id,
            'name': self.name or 'Folder',
            'subfolders': subfolders_data,
            'files': files_data
        }

    @property
    def folder_tree_json(self):
        import json
        return json.dumps(self.folder_tree)

    @property
    def all_files_json(self):
        import json, os
        data = []
        for f in self.all_files:
            if f.file:
                clean_name = os.path.basename(f.file.name)
                data.append({
                    'id': f.id,
                    'name': clean_name,
                    'raw_name': f.file.name,
                    'url': f.file.url,
                    'size': f.file_size_formatted
                })
        return json.dumps(data)

    def __str__(self):
        return str(self.name)

class Files(models.Model):
    folder = models.ForeignKey(Folders, on_delete=models.CASCADE, null=True, blank=True)
    file = models.FileField(null=True, blank=True, upload_to="files")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ['order', 'id']

    @property
    def file_size(self):
        if self.file:
            try:
                return self.file.size
            except Exception:
                return 0
        return 0

    @property
    def file_size_formatted(self):
        size = self.file_size
        if size == 0:
            return "0 B"
        import math
        size_name = ("B", "KB", "MB", "GB", "TB")
        i = int(math.floor(math.log(size, 1024)))
        p = math.pow(1024, i)
        s = round(size / p, 2)
        return f"{s} {size_name[i]}"

    def __str__(self):
        return f"{self.folder.name if self.folder else ''} {self.file.name if self.file else ''}"
