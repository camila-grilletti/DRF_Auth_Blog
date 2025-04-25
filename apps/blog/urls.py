from django.urls import path

from .views import (
    PostListView,
    PostDetailView,
    PostHeadingView,
    IncrementPostClickView,
    CategoryListView,
    CategoryDetailView,
    IncrementCategoryClickView,
    GenerateFakeAnalyticsView,
    GenerateFakePostsView,
    PostCommentViews,
    ListPostCommentsView,
    ListCommentRepliesView,
    CommentReplyViews,
    PostLikeViews,
    PostShareView,
    PostAuthorViews
)


urlpatterns = [
    path('generate_posts/', GenerateFakePostsView.as_view(), name='generate-fake-posts'),
    path('generate_analytics/', GenerateFakeAnalyticsView.as_view(), name='generate-fake-analytics'),
    path('posts/', PostListView.as_view(), name='posts-list'),
    path('post/', PostDetailView.as_view(), name='posts-detail'),
    path('post/headings/', PostHeadingView.as_view(), name='post-headings'),
    path('post/increment_click/', IncrementPostClickView.as_view(), name='increment-post-clicks'),
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('category/posts/', CategoryDetailView.as_view(), name='category-posts'),
    path('category/increment_click/', IncrementCategoryClickView.as_view(), name='increment-category-clicks'),
    path('post/comment/', PostCommentViews.as_view()),
    path('post/comments/', ListPostCommentsView.as_view()),
    path('post/comment/replies/', ListCommentRepliesView.as_view()),
    path('post/comment/reply/', CommentReplyViews.as_view()),
    path('post/like/', PostLikeViews.as_view()),
    path('post/share/', PostShareView.as_view()),
    path('post/author/', PostAuthorViews.as_view()),
]