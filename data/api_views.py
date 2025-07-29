from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
import requests

from data.models import Course, Exercise, Submission, Student, Comparison
from data.serializers import (
    CourseSerializer, ExerciseSerializer, SubmissionSerializer,
    StudentSerializer, ComparisonSerializer, ComparisonSummarySerializer
)
from django.conf import settings

class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing and retrieving courses
    """
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Course.objects.get_available_courses(self.request.user)


class ExerciseViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing and retrieving exercises
    """
    serializer_class = ExerciseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        course_key = self.kwargs.get('course_key')
        if course_key:
            course = get_object_or_404(Course, key=course_key)
            # Check user has access to course
            if not Course.objects.get_available_courses(self.request.user).filter(key=course_key).exists():
                return Exercise.objects.none()
            return course.exercises.all()
        return Exercise.objects.none()


class StudentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing and retrieving students
    """
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        course_key = self.kwargs.get('course_key')
        if course_key:
            course = get_object_or_404(Course, key=course_key)
            # Check user has access to course
            if not Course.objects.get_available_courses(self.request.user).filter(key=course_key).exists():
                return Student.objects.none()
            return Student.objects.filter(course=course)
        return Student.objects.none()


class SubmissionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing and retrieving submissions
    """
    serializer_class = SubmissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        course_key = self.kwargs.get('course_key')
        exercise_key = self.kwargs.get('exercise_key')

        if course_key:
            course = get_object_or_404(Course, key=course_key)
            # Check user has access to course
            if not Course.objects.get_available_courses(self.request.user).filter(key=course_key).exists():
                return Submission.objects.none()

            queryset = Submission.objects.filter(exercise__course=course)

            if exercise_key:
                exercise = get_object_or_404(Exercise, key=exercise_key, course=course)
                queryset = queryset.filter(exercise=exercise)

            return queryset.select_related('student', 'exercise')
        return Submission.objects.none()


class ComparisonViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing and retrieving comparisons
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return ComparisonSummarySerializer
        return ComparisonSerializer

    def get_queryset(self):
        course_key = self.kwargs.get('course_key')
        exercise_key = self.kwargs.get('exercise_key')

        if course_key:
            course = get_object_or_404(Course, key=course_key)
            # Check user has access to course
            if not Course.objects.get_available_courses(self.request.user).filter(key=course_key).exists():
                return Comparison.objects.none()

            queryset = Comparison.objects.filter(submission_a__exercise__course=course)

            if exercise_key:
                exercise = get_object_or_404(Exercise, key=exercise_key, course=course)
                queryset = queryset.filter(submission_a__exercise=exercise)

            # Filter by similarity threshold if provided
            min_similarity = self.request.query_params.get('min_similarity')
            if min_similarity:
                try:
                    queryset = queryset.filter(similarity__gte=float(min_similarity))
                except ValueError:
                    pass

            return queryset.select_related(
                'submission_a__student', 'submission_b__student',
                'submission_a__exercise', 'submission_b__exercise'
            ).order_by('-similarity')
        return Comparison.objects.none()

    @action(detail=False, methods=['get'])
    def flagged(self, request, course_key=None):
        """Get flagged comparisons (review >= 5)"""
        queryset = self.get_queryset().filter(review__gte=5)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


# Cheatersheet API proxy views
@api_view(['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@permission_classes([IsAuthenticated])
def cheatersheet_api_proxy(request, path=''):
    """
    Proxy API calls to cheatersheet service
    """
    try:
        # Get cheatersheet server URL from settings
        cheatersheet_url = getattr(settings, 'CHEATERSHEET_WEB_SERVER_URL', 'http://localhost:8072')
        token = getattr(settings, 'CHEATERSHEET_API_TOKEN', '')

        # Construct the target URL
        target_url = f"{cheatersheet_url.rstrip('/')}/api/{path.lstrip('/')}"

        # Prepare headers
        headers = {
            'Authorization': f'Token {token}',
            'Content-Type': 'application/json'
        }

        # Forward the request
        if request.method == 'GET':
            response = requests.get(
                target_url,
                params=request.GET.dict(),
                headers=headers
            )
        elif request.method == 'POST':
            response = requests.post(
                target_url,
                json=request.data,
                headers=headers
            )
        elif request.method == 'PUT':
            response = requests.put(
                target_url,
                json=request.data,
                headers=headers
            )
        elif request.method == 'PATCH':
            response = requests.patch(
                target_url,
                json=request.data,
                headers=headers
            )
        elif request.method == 'DELETE':
            response = requests.delete(
                target_url,
                headers=headers
            )
        else:
            return Response({'error': 'Method not allowed'}, status=405)

        # Return the response from cheatersheet
        try:
            return Response(response.json(), status=response.status_code)
        except ValueError:
            # Response is not JSON
            return HttpResponse(
                response.content,
                content_type=response.headers.get('Content-Type', 'text/plain'),
                status=response.status_code
            )

    except Exception as e:
        return Response({'error': str(e)}, status=500)
