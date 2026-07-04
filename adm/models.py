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

    def save(self, *args, **kwargs):
        # We only generate a thumbnail if there's an image and no thumbnail yet, or if you want to force it.
        # A simple approach is just to check if thumbnail is empty when image exists.
        if self.image and not self.thumbnail:
            try:
                img = Image.open(self.image)
                # Convert to RGB if it's RGBA and we are saving as JPEG
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                thumb_io = BytesIO()
                img_format = img.format if img.format else 'JPEG'
                if img_format == 'JPEG':
                    img.save(thumb_io, format='JPEG', quality=85)
                else:
                    img.save(thumb_io, format=img_format)
                thumb_name = os.path.basename(self.image.name)
                self.thumbnail.save(f"thumb_{thumb_name}", ContentFile(thumb_io.getvalue()), save=False)
            except Exception as e:
                print(f"Error generating thumbnail: {e}")
        elif not self.image:
            self.thumbnail = None
            
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.name)

class Files(models.Model):
    folder = models.ForeignKey(Folders, on_delete=models.CASCADE, null=True, blank=True)
    file = models.FileField(null=True, blank=True, upload_to="files")

    def __str__(self):
        return f"{self.folder.name if self.folder else ''} {self.file.name if self.file else ''}"
