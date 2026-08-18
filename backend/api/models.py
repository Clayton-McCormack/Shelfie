from django.db import models


class LibraryBook(models.Model):
    """One book explicitly accepted into the local library."""

    catalog_id = models.CharField(max_length=32, unique=True, null=True, blank=True)
    title = models.CharField(max_length=500)
    author = models.CharField(max_length=500, blank=True)
    decision = models.CharField(max_length=16)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-added_at']

    def __str__(self):
        return f'{self.title} — {self.author}'
