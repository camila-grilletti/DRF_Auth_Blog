from django.test import TestCase
from django.urls import reverse
from django.conf import settings
from django.core.cache import cache
from rest_framework.test import APIClient
from unittest.mock import patch

from .models import Category, Post, PostAnalytics, Heading

# -------------- MODELS TESTS --------------

class CategoryModelTest(TestCase):
    def setUp(self):
        cache.clear()
        self.category = Category.objects.create(
            name='Tech',
            title='Technology',
            description='All about technology',
            slug='tech'
        )

    def tearDown(self):
        cache.clear()
        
    def test_category_creation(self):
        self.assertEqual(str(self.category), 'Tech')
        self.assertEqual(str(self.category.title), 'Technology')


class PostModelTest(TestCase):
    def setUp(self):
        cache.clear()
        self.category = Category.objects.create(
            name='Tech',
            title='Technology',
            description='All about technology',
            slug='tech'
        )

        self.post = Post.objects.create(
            title='Post 1',
            description='A test post',
            content='Content for the post',
            thumbnail=None,
            keywords='test',
            slug='post-1',
            category=self.category,
            status='published',
        )

    def tearDown(self):
        cache.clear()
        
    def test_post_creation(self):
        self.assertEqual(str(self.post), 'Post 1')
        self.assertEqual(self.category.name, 'Tech')

    def test_post_published_manager(self):
        self.assertTrue(Post.postobjects.filter(status='published').exists())
        self.assertEqual(self.category.name, 'Tech')


class PostAnalyticsModelTest(TestCase):
    def setUp(self):
        cache.clear()
        self.category = Category.objects.create(
            name='Analytics',
            slug='analytics'
        )

        self.post = Post.objects.create(
            title='Post 1',
            description='A test post',
            content='Content for the post',
            thumbnail=None,
            keywords='test',
            slug='post-1',
            category=self.category,
            status='published',
        )

        self.analytics = PostAnalytics.objects.create(post=self.post)

    def tearDown(self):
        cache.clear()
        
    def test_click_through_rate(self):
        self.analytics.increment_impressions()
        self.analytics.increment_click()
        self.analytics.refresh_from_db()
        self.assertEqual(self.analytics.click_through_rate, 100.0)


class HeadingModelTest(TestCase):
    def setUp(self):
        cache.clear()
        self.category = Category.objects.create(
            name='Heading',
            slug='heading'
        )

        self.post = Post.objects.create(
            title='Post 1',
            description='A test post',
            content='Content for the post',
            thumbnail=None,
            keywords='test',
            slug='post-1',
            category=self.category,
            status='published',
        )

        self.heading = Heading.objects.create(
            post=self.post,
            title='Heading 1',
            slug='heading-1',
            level=1,
            order=1,
        )

    def tearDown(self):
        cache.clear()

    def test_heading_creation(self):
        self.assertEqual(self.heading.slug, 'heading-1')
        self.assertEqual(self.heading.level, 1)


# -------------- VIEWS TESTS --------------

class PostListViewTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        self.api_key = settings.VALID_API_KEYS[0]

        self.category = Category.objects.create(
            name='Tech',
            title='Technology'
        )

        self.post = Post.objects.create(
            title='Post 1',
            description='A test post',
            content='Content for the post',
            thumbnail=None,
            keywords='test',
            slug='post-1',
            category=self.category,
            status='published',
        )

    def tearDown(self):
        cache.clear()
    
    def test_get_post_list(self):
        url = reverse('posts-list')
        response = self.client.get(
            url,
            HTTP_API_KEY=self.api_key
        )

        data = response.json()
        print(data)

        self.assertIn('success', data)
        self.assertTrue(data['success'])
        self.assertIn('status', data)
        self.assertEqual(data['status'], 200)
        self.assertIn('results', data)
        self.assertEqual(data['count'], 1)

        results = data['results']
        self.assertEqual(len(results), 1)

        post_data = results[0]
        self.assertEqual(post_data['id'], str(self.post.id))
        self.assertEqual(post_data['title'], str(self.post.title))