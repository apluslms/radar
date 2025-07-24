from rest_framework import serializers
from data.models import Course, Exercise, Submission, Student, Comparison


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ['key', 'name', 'provider', 'created', 'updated']


class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = ['key', 'course', 'is_staff']


class ExerciseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exercise
        fields = [
            'key', 'name', 'course', 'paused', 'tokenizer', 
            'minimum_match_tokens', 'use_staff_submissions', 'created', 'updated'
        ]


class SubmissionSerializer(serializers.ModelSerializer):
    student = StudentSerializer(read_only=True)
    exercise = ExerciseSerializer(read_only=True)

    class Meta:
        model = Submission
        fields = [
            'id', 'key', 'exercise', 'student', 'filename', 'tokens',
            'max_similarity', 'grade', 'provider_submission_time', 'created'
        ]


class ComparisonSerializer(serializers.ModelSerializer):
    submission_a = SubmissionSerializer(read_only=True)
    submission_b = SubmissionSerializer(read_only=True)

    class Meta:
        model = Comparison
        fields = [
            'id', 'submission_a', 'submission_b', 'similarity', 
            'tokens', 'matches', 'review', 'created'
        ]


class ComparisonSummarySerializer(serializers.ModelSerializer):
    """Lighter serializer for comparisons without full submission details"""
    student_a_key = serializers.CharField(source='submission_a.student.key', read_only=True)
    student_b_key = serializers.CharField(source='submission_b.student.key', read_only=True)
    exercise_name = serializers.CharField(source='submission_a.exercise.name', read_only=True)

    class Meta:
        model = Comparison
        fields = [
            'id', 'student_a_key', 'student_b_key', 'exercise_name',
            'similarity', 'tokens', 'matches', 'review', 'created'
        ]
