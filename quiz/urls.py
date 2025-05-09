# quiz/urls.py
from django.urls import path
from .views import (
    QuestionAPI,
    RegisterAPI,
    LoginAPI,
    LogoutAPI,
    UserProfileAPI,
    RevisionQuestionAPI,
    SubmitAnswerAPI,
    TopicIntroductionAPI,
    SubjectTopicsAPI,
    TopicQuestionAPI,
    SessionAPI,
    ExpireSessionAPI,
    VerifyOTPAPI,
    ForgotPasswordAPI,
    ResetPasswordAPI,
)

urlpatterns = [
    path('questions/', QuestionAPI.as_view(), name='generate-question'),
    path('revision-questions/', RevisionQuestionAPI.as_view(), name='revision-questions'),
    path('auth/register/', RegisterAPI.as_view(), name='register'),
    path('auth/login/', LoginAPI.as_view(), name='login'),
    path('auth/logout/', LogoutAPI.as_view(), name='logout'),
    path('auth/profile/', UserProfileAPI.as_view(), name='user-profile'),
    path('submit-answer/', SubmitAnswerAPI.as_view(), name='submit-answer'),
    path('topic-introduction/', TopicIntroductionAPI.as_view(), name='topic-introduction'),
    path('subject-topics/<str:subject>/', SubjectTopicsAPI.as_view(), name='subject-topics'),
    # path('select-topic/', SelectTopicAPI.as_view(), name='select-topic'),
    path('topic-questions/', TopicQuestionAPI.as_view(), name='topic-questions'),
    path('sessions/', SessionAPI.as_view(), name='create-session'),
    path('sessions/<uuid:session_id>/expire/', ExpireSessionAPI.as_view(), name='expire-session'),
    path('auth/verify-otp/', VerifyOTPAPI.as_view(), name='verify-otp'),
    path('auth/forgot-password/', ForgotPasswordAPI.as_view(), name='forgot-password'),
    path('auth/reset-password/', ResetPasswordAPI.as_view(), name='reset-password'),
]