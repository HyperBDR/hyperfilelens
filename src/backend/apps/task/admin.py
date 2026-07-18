from django.contrib import admin

from apps.task.models import Task, TaskEvent, TaskResource, TaskStep


class TaskResourceInline(admin.TabularInline):
    model = TaskResource
    extra = 0
    fields = ("resource_type", "resource_id")


class TaskStepInline(admin.TabularInline):
    model = TaskStep
    extra = 0
    fields = ("step_index", "step_name", "status", "progress", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "task_uuid",
        "organization_id",
        "task_type",
        "display_name",
        "status",
        "progress",
        "trigger_type",
        "created_at",
        "updated_at",
    )
    list_filter = ("task_type", "status", "trigger_type")
    search_fields = ("task_uuid", "display_name", "error_code", "error_message")
    ordering = ("-created_at", "-id")
    inlines = (TaskResourceInline, TaskStepInline)


@admin.register(TaskEvent)
class TaskEventAdmin(admin.ModelAdmin):
    list_display = ("task", "step", "seq", "level", "created_at")
    list_filter = ("level",)
    search_fields = ("task__task_uuid", "message")
    ordering = ("-created_at", "-id")


admin.site.register(TaskResource)
admin.site.register(TaskStep)
