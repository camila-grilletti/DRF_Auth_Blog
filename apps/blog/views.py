from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.views import APIView
from rest_framework_api.views import StandardAPIView
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, APIException
import redis
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from django.db.models import Q, F, Prefetch
from django.shortcuts import get_object_or_404

from .models import Post, Heading, PostAnalytics, Category, CategoryAnalytics
from .serializers import PostListSerializer, PostSerializer, HeadingSerializer, CategoryListSerializer
from .tasks import increment_post_impressions
from .utils import get_client_ip
from .tasks import increment_post_views_tasks

from faker import Faker
import random
import uuid
from django.utils.text import slugify

from core.permissions import HasValidAPIKey

redis_client = redis.StrictRedis(host=settings.REDIS_HOST, port=6379, db=0)


class PostListView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def get(self, request, *args, **kwargs):
        try:
            search = request.query_params.get("search", "").strip()
            sorting = request.query_params.get("sorting", None)
            ordering = request.query_params.get("ordering", None)
            categories = request.query_params.getlist("category", [])
            page = request.query_params.getlist("p", "1")

            cache_key = f'post_list:{search}:{sorting}:{ordering}:{categories}:{page}'
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
        
        try:
            cached_post = cache.get(f'post_detail:{slug}')
            if cached_post:
                increment_post_views_tasks.delay(cached_post['slug'], ip_address)
                return self.response(cached_post)


            post = Post.postobjects.get(slug=slug)
            serialized_post = PostSerializer(post).data
            
            cache.set(f'post_detail:{slug}', serialized_post, timeout=60*5)

            increment_post_views_tasks.delay(post.slug, ip_address)


        except Post.DoesNotExist:
            raise NotFound(detail='The requested post does not exist.')
        except Exception as e:
            raise APIException(detail=f'An unexpected error ocurreed: {str(e)}')

        return self.response(serialized_post)
    

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
            post = Post(
                id=uuid.uuid4(),
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
    