from django.http import JsonResponse


def health(_request):
    return JsonResponse({"app": "notification", "status": "ok"})
