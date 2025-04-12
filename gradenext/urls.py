from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
def root_view(request):
    return JsonResponse({"status": "ok", "message": "🎉 GradeNext API is live!"})
urlpatterns = [
    path('', root_view),
    path('admin/', admin.site.urls),
    path('api/', include('quiz.urls')),
]