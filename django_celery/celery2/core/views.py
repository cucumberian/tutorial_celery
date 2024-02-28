from django.shortcuts import render
from django.views import View
from django.http import JsonResponse
from .tasks import task_process
from .models import Task


class IndexView(View):
    def get(self, request):
        return render(request, "core/index.html")


class AddTaskView(View):
    def post(self, request):
        value = request.POST.get("value")
        if value == "":
            return JsonResponse(
                {"status": "error", "message": "value is missing"}
            )
        task = Task(value=value)
        task.save()
        task_process.delay(task_id=task.id)
        return JsonResponse(
            {"status": "ok", "message": f"task {task.id} accepted"}
        )
