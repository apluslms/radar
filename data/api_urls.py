from django.urls import path, include
from rest_framework.routers import DefaultRouter
from data.api_views import (
    CourseViewSet, ExerciseViewSet, StudentViewSet,
    SubmissionViewSet, ComparisonViewSet,
    cheatersheet_api_proxy
)

router = DefaultRouter()
router.register(r'courses', CourseViewSet, basename='api-course')

course_router = DefaultRouter()
course_router.register(r'exercises', ExerciseViewSet, basename='api-exercise')
course_router.register(r'students', StudentViewSet, basename='api-student')
course_router.register(r'submissions', SubmissionViewSet, basename='api-submission')
course_router.register(r'comparisons', ComparisonViewSet, basename='api-comparison')

exercise_router = DefaultRouter()
exercise_router.register(r'submissions', SubmissionViewSet, basename='api-exercise-submission')
exercise_router.register(r'comparisons', ComparisonViewSet, basename='api-exercise-comparison')

urlpatterns = [
    path('', include(router.urls)),

    path('courses/<str:course_key>/', include(course_router.urls)),

    path('courses/<str:course_key>/exercises/<str:exercise_key>/', include(exercise_router.urls)),

    path('cheatersheet/', cheatersheet_api_proxy, name='api-cheatersheet-root'),
    path('cheatersheet/<path:path>', cheatersheet_api_proxy, name='api-cheatersheet-proxy'),
]
