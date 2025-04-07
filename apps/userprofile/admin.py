from django.contrib import admin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'profile_picture', 'birthday', 'website')
    search_fields = ('user__username', 'user__email', 'biography', 'website')
    list_filter = ('birthday',)
    ordering = ('user__username',)
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'birthday', 'biography')
        }),
        ('Profile Picture', {
            'fields': ('profile_picture', 'banner_picture')
        }),
        ('Social Links', {
            'fields': ('website', 'instagram', 'facebook', 'threads', 'linkedin', 'youtube', 'tiktok', 'github', 'gitlab')
        }),
    )
