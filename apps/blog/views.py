from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.views import APIView
from rest_framework_api.views import StandardAPIView
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, APIException, ValidationError
import redis
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from django.db.models import Q, F, Prefetch
from django.shortcuts import get_object_or_404

from .models import Post, Heading, PostAnalytics, Category, CategoryAnalytics, PostView, PostInteraction, Comment, PostLike, PostShare
from .serializers import PostListSerializer, PostSerializer, HeadingSerializer, CategoryListSerializer, CommentSerializer
from .utils import get_client_ip
from .tasks import increment_post_views_tasks
from apps.authentication.models import UserAccount
from utils.string_utils import sanitize_string, sanitize_html

from faker import Faker
import random
import uuid
from django.utils.text import slugify

from core.permissions import HasValidAPIKey

redis_client = redis.StrictRedis(host=settings.REDIS_HOST, port=6379, db=0)


class PostAuthorViews(StandardAPIView):
    permission_classes = [HasValidAPIKey, permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role == 'customer':
            return self.error('You do not have permissions to edit this post')

        posts = Post.objects.filter(user=user)
            
        if not posts.exists():
            raise NotFound(detail='No posts found.')

        serialized_posts = PostListSerializer(posts, many=True).data

        return self.paginate(request, serialized_posts)

    def post(self, request):

        user = request.user

        if user.role == 'customer':
            return self.error('You do not have permissions to edit this post')
        
        required_fields = ['title', 'content', 'slug', 'category']
        missing_fields = [
            field for field in required_fields if not request.data.get(field)
        ]

        if missing_fields:
            return self.error(f"Missing required fields: {', '.join(missing_fields)}")
        
        title = sanitize_string(request.data.get('title', None))
        description = sanitize_string(request.data.get('description', ""))
        content = sanitize_html(request.data.get('content', None))
        thumbnail = sanitize_string(request.data.get('thumbnail', None))
        keywords = sanitize_string(request.data.get('keywords', ""))
        slug = slugify(request.data.get('slug', None))
        category_slug = slugify(request.data.get('category', None))

        try:
            category = Category.objects.get(slug=category_slug)
        except Category.DoesNotExist:
            return self.response_error(
                f"Category '{category_slug}' does not exist.", status=400
            )
            
        try:
            post = Post.objects.create(
                user=user,
                title=title,
                description=description,
                content=content,
                keywords=keywords,
                slug=slug,
                category=category,
                thumbnail=thumbnail
            )

            headings = request.data.get("headings", [])
            for heading_data in headings:
                Heading.objects.create(
                    post=post,
                    title=heading_data.get('title'),
                    slug=heading_data.get('slug'),
                    level=heading_data.get('level'),
                    order=heading_data.get('order')
                )

        except Exception as e:
            return self.error(f"An error occurred: {str(e)}")
        
        return self.response(f"Post '{post.title}' created successfully. It will be shown in a few minutes.")
    
    def put(self, request):

        user = request.user

        if user.role == 'customer':
            return self.error('You do not have permissions to edit this post')
        
        post_slug = request.data.get('post_slug', None)

        if not post_slug:
            raise NotFound(detail="Post slug must ve provided.")

        try:
            post = Post.objects.get(slug=post_slug, user=user)
        except Post.DoesNotExist:
            raise NotFound(f"Post {post_slug} does not exist.")
        
        title = sanitize_string(request.data.get('title', None))
        post_status = sanitize_string(request.data.get('status', "draft"))
        description = sanitize_string(request.data.get('description', None))
        content = sanitize_html(request.data.get('content', None))
        thumbnail = sanitize_string(request.data.get('thumbnail', None))
        category_slug = slugify(request.data.get('category', post.category.slug))

        if category_slug:
            try:
                category = Category.objects.get(slug=category_slug)
                post.category = category

            except Category.DoesNotExist:
                return self.response_error(
                    f"Category '{category_slug}' does not exist.", status=400
                )

        if title:
            post.title = title

        if description:
            post.description = description

        if content:   
            post.content = content

        if thumbnail:
            post.thumbnail = thumbnail

        post.status = post_status

        headings = request.data.get("headings", [])
        if headings:
            post.headings.all().delete()

            for heading_data in headings:
                Heading.objects.create(
                    post=post,
                    title=heading_data.get('title'),
                    level=heading_data.get('level'),
                    order=heading_data.get('order')
                )

        post.save()

        return self.response(f"Post {post.title} successfully updated. Changes will be shown in a few minutes.")
    
    def delete(self, request):
        user = request.user

        if user.role == 'customer':
            return self.error('You do not have permissions to edit this post')
        
        post_slug = request.query_params.get('slug', None)

        if not post_slug:
            raise NotFound(detail="Post slug must ve provided.")

        try:
            post = Post.objects.get(slug=post_slug, user=user)
        except Post.DoesNotExist:
            raise NotFound(f"Post {post_slug} does not exist.")

        post.delete()

        return self.response(f"Post {post.title} successfully deleted.")


class PostListView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def get(self, request, *args, **kwargs):
        try:
            search = request.query_params.get("search", "").strip()
            sorting = request.query_params.get("sorting", None)
            ordering = request.query_params.get("ordering", None)
            author = request.query_params.get("author", None)
            categories = request.query_params.getlist("category", [])
            page = request.query_params.getlist("p", "1")

            cache_key = f'post_list:{search}:{sorting}:{ordering}:{author}:{categories}:{page}'
            cached_posts = cache.get(cache_key)
            
            if cached_posts:
                serialized_posts = PostListSerializer(cached_posts, many=True).data

                for post in cached_posts:
                    redis_client.incr(f'post:impressions:{post["id"]}')
                return self.paginate(request, serialized_posts)
            
            posts = Post.postobjects.all().select_related("category").prefetch_related(
                Prefetch("post_analytics", to_attr="analytics_cache")
            )
            
            if not posts.exists():
                raise NotFound(detail='No posts found.')

            if search != "":
                posts = Post.postobjects.filter(
                    Q(title__icontains=search) |
                    Q(description__icontains=search) |
                    Q(content__icontains=search) |
                    Q(keywords__icontains=search)
                )
            
            if author:
                posts = posts.filter(user__username=author)

            if categories:
                category_queries = Q()
                for category in categories:
                    try:
                        uuid.UUID(category)
                        uuid_query = (
                            Q(category__id=category)
                        )
                        category_queries |= uuid_query
                    except:
                        slug_query = (
                            Q(category__slug=category)
                        )
                        category_queries |= slug_query
                
                posts = posts.filter(category_queries)

            if sorting:
                if sorting == 'newest':
                    posts = posts.order_by("-created_at")
                elif sorting == 'recently_updated':
                    posts = posts.order_by('-updated_at')
                elif sorting == 'most_viewed':
                    posts = posts.annotate(popularity=F("analytics_cache__views")).order_by('-popularity')

            if ordering:
                if ordering == 'az':
                    posts = posts.order_by("title")
                elif ordering == 'za':
                    posts = posts.order_by('-title')

            cache.set(cache_key, posts, timeout=60*5)

            serialized_posts = PostListSerializer(posts, many=True).data

            for post in posts:
                redis_client.incr(f'post:impressions:{post.id}')
    
            return self.paginate(request, serialized_posts)

        except Post.DoesNotExist:
            raise NotFound(detail='No posts found.')
        except Exception as e:
            raise APIException(detail=f'An unexpected error ocurreed: {str(e)}')
            

class PostDetailView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def get(self, request):
        ip_address = get_client_ip(request)
        slug = request.query_params.get('slug')
        user = request.user if request.user.is_authenticated else None

        if not slug:
            raise NotFound(detail='A valid slug muest be provided.')
        
        try:            
            cache_key = f'post_detail:{slug}'
            cached_serialized_post = cache.get(cache_key)
            
            if cached_serialized_post:
                serialized_post = PostSerializer(cached_serialized_post, context={'request': request}).data
                self._register_view_interaction(cached_serialized_post, ip_address, user)
                return self.response(serialized_post)
            
            try:
                post = Post.postobjects.get(slug=slug)
            except Post.DoesNotExist:
                raise NotFound(f"Post {slug} does not exist.")

            serialized_post = PostSerializer(post, context={'request': request}).data

            cache.set(cache_key, serialized_post, timeout=60*5)
            cache.delete(cache_key)

            self._register_view_interaction(post, ip_address, user)
            
        except Post.DoesNotExist:
            raise NotFound(detail='The requested post does not exist.')
        except Exception as e:
            raise APIException(detail=f'An unexpected error ocurreed: {str(e)}')

        return self.response(serialized_post)
    
    def _register_view_interaction(self, post, ip_address, user):
        # Register view type interaction, increments unique and total views and updates PostAnalytics

        if not PostView.objects.filter(post=post, ip_address=ip_address, user=user).exists():
            PostView.objects.create(post=post, ip_address=ip_address, user=user)

            PostInteraction.objects.create(
                user=user,
                post=post,
                interaction_type='view',
                ip_address=ip_address,
            )

            analytics, _ = PostAnalytics.objects.get_or_create(post=post)
            analytics.increment_metric('views')


class PostHeadingView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def get(self, request):
        post_slug = request.query_params.get('slug')
        heading_objects = Heading.objects.filter(post__slug=post_slug)
        serializer_data = HeadingSerializer(heading_objects, many=True).data
        return self.response(serializer_data)
    

class IncrementPostClickView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def post(self, request):
        data = request.data

        try:
            post = Post.postobjects.get(slug=data['slug'])
        except Post.DoesNotExist:
            raise NotFound(detail='The requested post does not exist.')
        
        try:
            post_analytics, created = PostAnalytics.objects.get_or_create(post=post)
            post_analytics.increment_click()
        except Exception as e:
            raise APIException(detail=f'An unexpected error ocurreed: {str(e)}')
        
        return self.response({
            'message': 'Click incremented successfully',
            'clicks': post_analytics.clicks
        })


class CategoryListView(StandardAPIView):
    def get(self, request):
        try:
            parent_slug = request.query_params.get("parent_slug", None)
            search = request.query_params.get("search", "").strip()
            ordering = request.query_params.get("ordering", None)
            sorting = request.query_params.get("sorting", None)
            page = request.query_params.get("p", "1")

            cache_key = f'category_list:{page}:{ordering}:{sorting}:{search}:{parent_slug}'
            cached_categories = cache.get(cache_key)
            
            if cached_categories:
                serialized_categories = CategoryListSerializer(categories, many=True).data

                for category in cached_categories:
                    redis_client.incr(f'category:impressions:{category["id"]}')
                return self.paginate(request, serialized_categories)

            if parent_slug:
                categories = Category.objects.filter(parent__slug=parent_slug).prefetch_related(
                    Prefetch("category_analytics", to_attr="analytics_cache")
                )
            else:
                categories = Category.objects.filter(parent__isnull=True).prefetch_related(
                    Prefetch("category_analytics", to_attr="analytics_cache")
                )

            if not categories.exists():
                raise NotFound(detail="No categories found.")
            
            if search != "":
                categories = Category.objects.filter(
                    Q(name__icontains=search) |
                    Q(slug__icontains=search) |
                    Q(title__icontains=search) |
                    Q(description__icontains=search)
                )

            if sorting:
                if sorting == 'newest':
                    categories = categories.order_by("-created_at")
                elif sorting == 'recently_updated':
                    categories = categories.order_by('-updated_at')
                elif sorting == 'most_viewed':
                    categories = categories.annotate(popularity=F("analytics_cache__views")).order_by('-popularity')

            if ordering:
                if ordering == 'az':
                    categories = categories.order_by("name")
                elif ordering == 'za':
                    categories = categories.order_by('-name')

            cache.set(cache_key, categories, timeout=60*5)

            serialized_categories = CategoryListSerializer(categories, many=True).data

            for category in categories:
                redis_client.incr(f'category:impressions:{category.id}')
            
            return self.paginate(request, serialized_categories)
        
        except Category.DoesNotExist:
            raise NotFound(detail='No categories found.')
        except Exception as e:
            raise APIException(detail=f'An unexpected error ocurreed: {str(e)}')


class CategoryDetailView(StandardAPIView):
    permissions_classes = [HasValidAPIKey]

    def get(self, request):
        try:
            slug = request.query_params.get('slug', None)
            page = request.query_params.get('p', '1')

            if not slug:
                return self.error("Missing slug parameter")
            
            cache_key = f"category_posts:{slug}:{page}"
            cached_data = cache.get(cache_key)
            
            if cached_data:
                return self.paginate(request, cached_data)
            
            category = get_object_or_404(Category, slug=slug)

            posts = Post.postobjects.filter(category=category).select_related('category').prefetch_related(
                Prefetch("post_analytics", to_attr="analytics_cache")
            )

            if not posts.exists():
                raise NotFound(detail=f"No posts found for category '{category.name}'.")
            
            serialized_posts = PostListSerializer(posts, many=True).data
            
            cache.set(cache_key, serialized_posts, timeout=60*5)

            for post in posts:
                redis_client.incr(f'post:impressions:{post.id}')

            return self.paginate(request, serialized_posts)
        
        except Category.DoesNotExist:
            raise NotFound(detail='No categories found.')
        except Exception as e:
            raise APIException(detail=f'An unexpected error occurred: {str(e)}')
        

class IncrementCategoryClickView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def category(self, request):
        data = request.data

        try:
            category = Category.objects.get(slug=data['slug'])
        except Category.DoesNotExist:
            raise NotFound(detail='The requested category does not exist.')
        
        try:
            category_analytics, created = CategoryAnalytics.objects.get_or_create(category=category)
            category_analytics.increment_click()
        except Exception as e:
            raise APIException(detail=f'An unexpected error ocurreed: {str(e)}')
        
        return self.response({
            'message': 'Click incremented successfully',
            'clicks': category_analytics.clicks
        })


class ListPostCommentsView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def get(self, request):
        """ List comments of a post """

        post_slug = request.query_params.get('slug', None)
        page = request.query_params.get("p", "1")

        if not post_slug:
            raise NotFound(detail='A valid post slug must be provided.')

        cache_key = f"post_comment:{post_slug}:{page}"
        cached_comments = cache.get(cache_key)

        if cached_comments:
            return self.paginate(request, cached_comments)

        try:
            post = Post.objects.get(slug=post_slug)
        except Post.DoesNotExist:
            raise ValueError(f"Post: {post_slug} does not exist")
        
        comments = Comment.objects.filter(post=post)
        serialized_comments = CommentSerializer(comments, many=True).data

        cache_index_key = f"post_comments_cache_keys:{post_slug}"
        cache_keys = cache.get(cache_index_key, [])
        cache_keys.append(cache_key)

        cache.set(cache_index_key, cache_keys, timeout=60*5)

        cache.set(cache_key, serialized_comments, timeout=60*5)

        return self.paginate(request, serialized_comments)


class PostCommentViews(StandardAPIView):
    permission_classes = [HasValidAPIKey, permissions.IsAuthenticated]

    def post(self, request):

        post_slug = request.data.get('slug', None)
        user = request.user
        ip_address = get_client_ip(request)
        content = sanitize_html(request.data.get('content', None))

        if not post_slug:
            raise NotFound(detail='A valid post slug must be provided.')
        
        try:
            post = Post.objects.get(slug=post_slug)
        except Post.DoesNotExist:
            raise NotFound(detail=f"Post: {post_slug} does not exist")
        
        comment = Comment.objects.create(
            user=user,
            post=post,
            content=content,
        )

        self._invalidate_post_comments_cache(post_slug)

        self._register_view_interaction(comment, post, ip_address, user)

        return self.response(f"Comment created for post {post.title}")

    def put(self, request):

        comment_id = request.data.get('comment_id', None)
        user = request.user
        content = sanitize_html(request.data.get('content', None))

        if not comment_id:
            raise NotFound(detail='A valid comment id must be provided.')
        
        try:
            comment = Comment.objects.get(id=comment_id, user=user)
        except Comment.DoesNotExist:
            raise ValueError(f"Comment with id: {comment_id} does not exist")
        
        comment.content = content
        comment.save()

        self._invalidate_post_comments_cache(comment.post.slug)

        if comment.parent and comment.parent.replies.exist():
            self._invalidate_comment_replies_cache(comment.parent.id)

        return self.response('Comment content updated successfully.')

    def delete(self, request):

        comment_id = request.query_params.get('comment_id', None)

        if not comment_id:
            raise NotFound(detail='A valid comment id must be provided.')
        
        try:
            comment = Comment.objects.get(id=comment_id, user=request.user)
        except Comment.DoesNotExist:
            raise NotFound(detail=f"Comment with id: {comment_id} does not exist")

        post = comment.post
        post_analytics, _ = PostAnalytics.objects.get_or_create(post=post)

        if comment.parent and comment.parent.replies.exist():
            self._invalidate_comment_replies_cache(comment.parent.id)

        comment.delete()

        comments_count = Comment.objects.filter(post=post, is_active=True).count()

        post_analytics.comments = comments_count
        post_analytics.save()

        self._invalidate_post_comments_cache(post.slug)

        return self.response('Comment deleted successfully.')
    
    def _register_view_interaction(self, comment, post, ip_address, user):
        # Register view type interaction, increments unique and total views and updates PostAnalytics

        PostInteraction.objects.create(
            user=user,
            post=post,
            interaction_type='comment',
            comment=comment,
            ip_address=ip_address,
        )

        analytics, _ = PostAnalytics.objects.get_or_create(post=post)
        analytics.increment_metric('comments')

    def _invalidate_post_comments_cache(self, post_slug):
        cache_index_key = f"post_comments_cache_keys:{post_slug}"
        cache_keys = cache.get(cache_index_key, [])

        for key in cache_keys:
            cache.delete(key)

        cache.delete(cache_index_key)

    def _invalidate_comment_replies_cache(self, comment_id):
        cache_index_key = f"comment_replies_cache_keys:{comment_id}"
        cache_keys = cache.get(cache_index_key, [])

        for key in cache_keys:
            cache.delete(key)

        cache.delete(cache_index_key)


class ListCommentRepliesView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def get(self, request):

        comment_id = request.query_params.get("comment_id", None)
        page = request.query_params.get("p", 1)

        if not comment_id:
            raise NotFound(detail='A valid comment id must be provided.')
        
        cache_key = f"comment_replies:{comment_id}:{page}"
        cached_replies = cache.get(cache_key)

        if cached_replies:
            return self.paginate(request, cached_replies)
        
        try:
            parent_comment = Comment.objects.get(id=comment_id)
        except Comment.DoesNotExist:
            raise NotFound(detail=f"Comment with id: {comment_id} does not exist")
        
        replies = parent_comment.replies.filter(is_active=True).order_by("-created_at")

        serialized_replies = CommentSerializer(replies, many=True).data

        self._register_comment_reply_cache_key(comment_id, cache_key)

        cache.set(cache_key, serialized_replies, timeout=60*5)

        return self.paginate(request, serialized_replies)
    
    def _register_comment_reply_cache_key(self, comment_id, cache_key):
        cache_index_key = f"comment_replies_cache_keys:{comment_id}"
        cache_keys = cache.get(cache_index_key, [])

        if cache_key not in cache_keys:
            cache_keys.append(cache_key)

        cache.set(cache_index_key, cache_keys, timeout=60*5)


class CommentReplyViews(StandardAPIView):
    permission_classes = [HasValidAPIKey, permissions.IsAuthenticated]
    
    def post(self, request):

        comment_id = request.data.get("comment_id")
        user = request.user
        ip_address = get_client_ip(request)
        content = sanitize_html(request.data.get('content', None))

        if not comment_id:
            raise NotFound(detail='A valid comment id must be provided.')

        try:
            parent_comment = Comment.objects.get(id=comment_id)
        except Comment.DoesNotExist:
            raise NotFound(detail=f"Comment with id {comment_id} does not exist.")

        comment = Comment.objects.create(
            user=user,
            post=parent_comment.post,
            parent=parent_comment,
            content=content,
        )

        self._invalidate_comment_replies_cache(comment_id)

        self._register_view_interaction(comment, comment.post, ip_address, user)

        return self.response("Comment reply created successfully")
    
    def _invalidate_comment_replies_cache(self, comment_id):
        cache_index_key = f"comment_replies_cache_keys:{comment_id}"
        cache_keys = cache.get(cache_index_key, [])

        for key in cache_keys:
            cache.delete(key)

        cache.delete(cache_index_key)

    def _register_view_interaction(self, comment, post, ip_address, user):
        # Register view type interaction, increments unique and total views and updates PostAnalytics

        PostInteraction.objects.create(
            user=user,
            post=post,
            interaction_type='comment',
            comment=comment,
            ip_address=ip_address,
        )

        analytics, _ = PostAnalytics.objects.get_or_create(post=post)
        analytics.increment_metric('comments')


class PostLikeViews(StandardAPIView):
    permission_classes = [HasValidAPIKey, permissions.IsAuthenticated]

    def post(self, request):

        post_slug = request.data.get("slug", None)
        user = request.user

        ip_address = get_client_ip(request)

        if not post_slug:
            raise NotFound(detail='A valid post slug must be provided.')
        
        try:
            post = Post.objects.get(slug=post_slug)
        except Post.DoesNotExist:
            raise NotFound(detail=f"Post: {post_slug} does not exist")
        
        if PostLike.objects.filter(post=post, user=user).exists():
            raise ValidationError(detail="You have already liked this post.")
        
        PostLike.objects.create(post=post, user=user)

        PostInteraction.objects.create(
            user=user,
            post=post,
            interaction_type='like',
            ip_address=ip_address,
        )

        analytics, _ = PostAnalytics.objects.get_or_create(post=post)
        analytics.increment_metric("likes")


        return self.response(f"You have liked the post: {post.title}")
    
    def delete(self, request):

        post_slug = request.query_params.get('slug', None)
        user = request.user

        if not post_slug:
            raise NotFound(detail='A valid post slug must be provided.')
        
        try:
            post = Post.objects.get(slug=post_slug)
        except Post.DoesNotExist:
            raise NotFound(detail=f"Post: {post_slug} does not exist")
        
        try:
            like = PostLike.objects.get(post=post, user=user)
        except PostLike.DoesNotExist:
            raise ValidationError(detail=f"You have not liked this post.")
        
        like.delete()

        analytics, _ = PostAnalytics.objects.get_or_create(post=post)
        analytics.likes = PostLike.objects.filter(post=post).count()
        analytics.save()

        return self.response(f"You have unliked the post: {post.title}")


class PostShareView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def post(self, request):

        post_slug = request.data.get('slug', None)
        platform = request.data.get('platform', 'other').lower()
        user = request.user if request.user.is_authenticated else None
        ip_address = get_client_ip(request)

        if not post_slug:
            raise NotFound(detail='A valid post slug must be provided')
        
        try:
            post = Post.objects.get(slug=post_slug)
        except Post.DoesNotExist:
            raise NotFound(detail=f"Post: {post_slug} does not exist")
        
        valid_platforms = [choice[0] for choice in PostShare._meta.get_field('platform').choices]

        if platform not in valid_platforms:
            raise ValidationError(detail=f'Invalid platform. Valid options are: {', '.join(valid_platforms)}')
        
        PostShare.objects.create(
            post=post,
            user=user,
            platform=platform
        )

        PostInteraction.objects.create(
            user=user,
            post=post,
            interaction_type='share',
            ip_address=ip_address
        )
        
        analytics, _ = PostAnalytics.objects.get_or_create(post=post)
        analytics.increment_metric('shares')

        return self.response(f'Post {post.title} shared successfully on {platform.capitalize()}')


class GenerateFakePostsView(StandardAPIView):

    def get(self, request):

        fake = Faker()

        categories = list(Category.objects.all())

        if not categories:
            return self.response("No categories availables for posts", 400)
        
        posts_to_generate = 100
        status_options = ["draft", "published"]

        for _ in range(posts_to_generate):
            title = fake.sentence(nb_words=6)
            user = UserAccount.objects.get(username='testeditor')
            post = Post(
                id=uuid.uuid4(),
                user=user,
                title=title,
                description=fake.sentence(nb_words=12),
                content=fake.paragraph(nb_sentences=4),
                keywords=", ".join(fake.words(nb=5)),
                slug=slugify(title),
                category=random.choice(categories),
                status=random.choice(status_options),
            )
            post.save()

        return self.response(f"{posts_to_generate} posts generated successfully.")
    

class GenerateFakeAnalyticsView(StandardAPIView):

    def get(self, request):

        posts = Post.objects.all()

        if not posts:
            return self.response("No posts availables for analytics", 400)
        
        analytics_to_generate = len(posts)

        for post in posts:
            views = random.randint(50, 1000)
            impressions = views + random.randint(100, 2000)
            clicks = random.randint(0, views)
            avg_time_on_page = round(random.uniform(10, 300), 2)

            analytics, created = PostAnalytics.objects.get_or_create(post=post)
            analytics.views = views
            analytics.impressions = impressions
            analytics.clicks = clicks
            analytics.avg_time_on_page = avg_time_on_page
            analytics._update_click_through_rate()
            analytics.save()

        return self.response(f"{analytics_to_generate} analytics generated successfully.")
    