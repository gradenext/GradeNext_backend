# quiz/urls.py
from django.urls import path
from .views import (
    QuestionAPI,
    RegisterAPI,
    LoginAPI,
    LogoutAPI,
    UserProfileAPI,
    RevisionQuestionAPI,
    SubmitAnswerAPI
)

urlpatterns = [
    path('questions/', QuestionAPI.as_view(), name='generate-question'),
    path('revision-questions/', RevisionQuestionAPI.as_view(), name='revision-questions'),
    path('auth/register/', RegisterAPI.as_view(), name='register'),
    path('auth/login/', LoginAPI.as_view(), name='login'),
    path('auth/logout/', LogoutAPI.as_view(), name='logout'),
    path('auth/profile/', UserProfileAPI.as_view(), name='user-profile'),
    path('submit-answer/', SubmitAnswerAPI.as_view(), name='submit-answer'),
]