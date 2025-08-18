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

class ProposerNotification(Notification):
    user = models.ForeignKey(
        'accounts.Proposer',
        on_delete=models.CASCADE,
        related_name='proposer_notification',
    )

    def __str__(self):
        return f'{self.user.user.email} 님, {self.body}'

class FounderNotification(Notification):
    user = models.ForeignKey(
        'accounts.Founder',
        on_delete=models.CASCADE,
        related_name='founder_notification',
    )

    def __str__(self):
        return f'{self.user.user.email} 님, {self.body}'
