import uuid
from ckeditor.fields import RichTextField
from djoser.signals import user_registered, user_activated

from django.db import models
from django.conf import settings


User = settings.AUTH_USER_MODEL


class UserProfile(models.Model):

    id = models.UUIDField(default=uuid.uuid4, unique=True, primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # banner_picture = models.ForeignKey()
    biography = RichTextField()
    birthday = models.DateField(blank=True, null=True)

    website = models.URLField(blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    youtube = models.URLField(blank=True, null=True)
    facebook = models.URLField(blank=True, null=True)
    threads = models.URLField(blank=True, null=True)
    linkedin = models.URLField(blank=True, null=True)
    tiktok = models.URLField(blank=True, null=True)
    github = models.URLField(blank=True, null=True)
    gitlab = models.URLField(blank=True, null=True)


# def post_user_registered(user, *args, **kwargs):
#     print('User has been registered.')

def post_user_activated(user, *args, **kwargs):
    profile = UserProfile.objects.create(user=user)


# user_registered.connect(post_user_registered)
user_activated.connect(post_user_activated)

