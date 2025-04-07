import uuid
from ckeditor.fields import RichTextField
from djoser.signals import user_registered, user_activated
from django.db.models.signals import post_save
from django.dispatch import receiver

from django.db import models
from django.conf import settings


User = settings.AUTH_USER_MODEL


def profile_picture_thumbnail_directory(instance, filename):
    return "thumbnails/userprofile_profile_picture/{0}/{1}".format(instance.name, filename)


def banner_picture_thumbnail_directory(instance, filename):
    return "thumbnails/userprofile_banner_picture/{0}/{1}".format(instance.name, filename)


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

    profile_picture = models.ImageField(upload_to=profile_picture_thumbnail_directory, blank=True, null=True)
    banner_picture = models.ImageField(upload_to=banner_picture_thumbnail_directory, blank=True, null=True)



@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Creates an user profile each time a new user is created.
    """
    if created:
        profile = UserProfile.objects.create(user=instance)
        # TODO: Save profile and banner image.
        profile.save()
