from django.db import models

class Folders(models.Model):
    parent_folder = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return str(self.name)


class Files(models.Model):
    folder = models.ForeignKey(Folders, on_delete=models.CASCADE, null=True, blank=True)
    file = models.FileField(null=True, blank=True, upload_to="files")

    def __str__(self):
        return f"{self.folder.name if self.folder else ''} {self.file.name if self.file else ''}"
