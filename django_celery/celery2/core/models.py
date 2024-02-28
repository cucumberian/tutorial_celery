from django.db import models


class Task(models.Model):
    value = models.CharField(max_length=200)
    is_completed = models.BooleanField(default=False)
    result = models.CharField(
        max_length=200, default="", null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"[{self.id}]: {self.value}"