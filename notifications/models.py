from django.db import models
from utils.choices import NotificationCategoryChoices

class Notification(models.Model):
    body = models.CharField(
        max_length=65,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    category = models.CharField(
        max_length=7,
        choices=NotificationCategoryChoices.choices,
    )
    path_variable = models.CharField(
        max_length=21,
    )

    class Meta:
        abstract = True
