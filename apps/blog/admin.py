from django.contrib import admin

from .models import (
    Category,
    Post,
    Heading,
    PostAnalytics,
    CategoryAnalytics,
    PostInteraction,
    Comment,
    PostLike,
    PostShare,
    PostView,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'title', 'parent', 'slug')
    search_fields = ('name', 'title', 'description', 'slug')
    prepopulated_fields = { 'slug': ('name',) }
    list_filter = ('parent',)
    ordering = ('name',)
    readonly_fields = ('id',)
    list_editable = ('title',)


@admin.register(CategoryAnalytics)
class CategoryAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('category_name', 'views', 'impressions', 'clicks', 'click_through_rate', 'avg_time_on_page')
    search_fields = ('category_name',)
    readonly_fields = ('category', 'views', 'impressions', 'clicks', 'click_through_rate', 'avg_time_on_page')

    def category_name(self, obj):
        return obj.category.name
    
    category_name.short_description = 'Category Name'


class HeadingInline(admin.TabularInline):
    model = Heading
    extra = 1
    fields = ('title', 'level', 'order', 'slug')
    prepopulated_fields = {'slug': ('title',)}
    ordering = ('order',)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'category', 'created_at', 'updated_at')
    search_fields = ('title', 'description', 'content', 'keywords' 'slug')
    prepopulated_fields = { 'slug': ('title',) }
    list_filter = ('status', 'category', 'updated_at',)
    ordering = ('-created_at',)
    readonly_fields = ('id', 'created_at', 'updated_at')
    fieldsets = (
        ('General Information', {
            'fields': ('title', 'description', 'content', 'thumbnail', 'keywords', 'slug', 'category', 'user')
        }),
        ('Status & Dates', {
            'fields': ('status', 'created_at', 'updated_at')
        }),
    )
    inlines = [HeadingInline]


@admin.register(Heading)
class HeadingAdmin(admin.ModelAdmin):
    list_display = ('title', 'post', 'level', 'order')
    search_fields = ('title', 'post__title')
    list_filter = ('level', 'post')
    ordering = ('post', 'order',)
    prepopulated_fields = { 'slug': ('title',) }


@admin.register(PostAnalytics)
class PostAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('post_title', 'views', 'impressions', 'clicks', 'click_through_rate', 'avg_time_on_page', 'likes', 'comments', 'shares')
    search_fields = ('post__title',)
    readonly_fields = ('post', 'views', 'impressions', 'clicks', 'click_through_rate', 'avg_time_on_page', 'likes', 'comments', 'shares')

    def post_title(self, obj):
        return obj.post.title
    
    post_title.short_description = 'Post Title'


@admin.register(PostInteraction)
class PostInteractionAdmin(admin.ModelAdmin):
    list_display = ('user', 'post', 'interaction_type', 'timestamp')
    search_fields = ('user__username', 'post__title', 'interaction_type')
    list_filter = ('interaction_type', 'timestamp')
    ordering = ('-timestamp',)
    readonly_fields = ('id', 'timestamp')

    def post_title(self, obj):
        return obj.post.title
    
    post_title.short_description = 'Post Title'


admin.site.register(PostLike)
admin.site.register(PostView)
admin.site.register(PostShare)

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'post', 'created_at', 'is_active')
    search_fields = ('user__username', 'post__title', 'content')
    list_filter = ('is_active', 'created_at')
    readonly_fields = ('id', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    list_display_links = ('id', 'user')