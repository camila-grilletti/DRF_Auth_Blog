from rest_framework import serializers

from .models import (
    Post, 
    Category, 
    Heading, 
    PostView, 
    PostInteraction, 
    Comment, 
    PostLike, 
    PostShare,
    CategoryAnalytics,
    PostAnalytics,
)


class CategorySerializer(serializers.ModelSerializer):    
    class Meta:
        model = Category
        fields = '__all__'


class CategoryListSerializer(serializers.ModelSerializer):        
    class Meta:
        model = Category
        fields = [
            'name',
            'slug',
        ]


class CategoryAnalyticsSerializer(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()

    class Meta:
        model = CategoryAnalytics
        fields = [
            'id',
            'category_name',
            'views',
            'impressions',
            'clicks',
            'click_through_rate',
            'avg_time_on_page',
        ]

    def get_category_name(self, obj):
        return obj.category.name


class HeadingSerializer(serializers.ModelSerializer):    
    class Meta:
        model = Heading
        fields = [
            'title',
            'slug',
            'level',
            'order',
        ]


class PostViewSerializer(serializers.ModelSerializer):    
    class Meta:
        model = PostView
        fields = '__all__'


class PostSerializer(serializers.ModelSerializer):    
    category = CategorySerializer() 
    headings = HeadingSerializer(many=True) 
    comments_count = serializers.SerializerMethodField()
    likes_count = serializers.SerializerMethodField()
    has_liked = serializers.SerializerMethodField()
    view_count = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = '__all__'

    def get_view_count(self, obj):
        return obj.post_analytics.views if obj.post_analytics else 0
    
    def get_comments_count(self, obj):
        return obj.post_comments.filter(parent=None, is_active=True).count()
    
    def get_likes_count(self, obj):
        return obj.likes.filter().count()
    
    def get_has_liked(self, obj):
        user = self.context.get('request').user

        if user and user.is_authenticated:
            return PostLike.objects.filter(post=obj, user=user).exists()
        
        return False
    

class PostListSerializer(serializers.ModelSerializer):
    category = CategorySerializer() 
    view_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Post
        fields = [
            'id',
            'title',
            'description',
            'thumbnail',
            'slug',
            'category',
            'view_count'
        ]

    def get_view_count(self, obj):
        return obj.post_analytics.views if obj.post_analytics else 0


class PostAnalyticsSerializer(serializers.Serializer):
    post_title = serializers.SerializerMethodField()
    
    class Meta:
        model = PostAnalytics
        fields = [
            'id',
            'post_title',
            'impressions',
            'clicks',
            'click_through_rate',
            'avg_time_on_page',
            'views',
            'likes',
            'comments',
            'shares',
        ]

    def get_post_title(self, obj):
        return obj.post.title


class PostInteractionSerializer(serializers.Serializer):
    user = serializers.StringRelatedField()
    post_title = serializers.SerializerMethodField()
    comment_content = serializers.SerializerMethodField()

    def get_post_title(self, obj):
        return obj.post.title
    
    def get_comment_content(self, obj):
        return obj.comment.content if obj.content else None
    
    class Meta:
        model = PostInteraction
        fields = [
            'id',
            'user',
            'post',
            'post_title',
            'interaction_type',
            'interaction_category',
            'weight',
            'timestamp',
            'device_type',
            'ip_address',
            'hour_of_day',
            'day_of_week',
            'comment_content',
        ]


class CommentSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    post_title = serializers.SerializerMethodField()
    replies_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = [
            'id',
            'user',
            'post',
            'post_title',
            'parent',
            'content',
            'created_at',
            'updated_at',
            'is_active',
            'replies_count',
        ]

    def get_post_title(self, obj):
        return obj.post.title
    
    def get_replies_count(self, obj):
        return obj.replies.filter(is_active=True).count()


class PostLikeSerializer(serializers.Serializer):
    user = serializers.StringRelatedField()
    
    class Meta:
        model = PostLike
        fields = [
            'id',
            'user',
            'post',
            'timestamp',
        ]


class PostShareSerializer(serializers.Serializer):
    user = serializers.StringRelatedField()
    
    class Meta:
        model = PostShare
        fields = [
            'id',
            'user',
            'post',
            'platform',
            'timestamp',
        ]
