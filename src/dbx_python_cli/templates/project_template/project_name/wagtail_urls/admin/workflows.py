# Copied from wagtail/admin/urls/workflows.py (Wagtail 7.3.1)
# <int: path converters replaced with <object_id: for Django MongoDB Backend compatibility.
# Re-diff against upstream on Wagtail upgrades.
from django.urls import path

from wagtail.admin.views import workflows

app_name = "wagtailadmin_workflows"
urlpatterns = [
    path("list/", workflows.Index.as_view(), name="index"),
    path(
        "list/results/",
        workflows.Index.as_view(results_only=True),
        name="index_results",
    ),
    path("add/", workflows.Create.as_view(), name="add"),
    path("enable/<object_id:pk>/", workflows.enable_workflow, name="enable"),
    path("disable/<object_id:pk>/", workflows.Disable.as_view(), name="disable"),
    path("edit/<object_id:pk>/", workflows.Edit.as_view(), name="edit"),
    path("usage/<object_id:pk>/", workflows.WorkflowUsageView.as_view(), name="usage"),
    path(
        "usage/<object_id:pk>/results/",
        workflows.WorkflowUsageView.as_view(results_only=True),
        name="usage_results",
    ),
    path("remove/<object_id:page_pk>/", workflows.remove_workflow, name="remove"),
    path(
        "remove/<object_id:page_pk>/<object_id:workflow_pk>/",
        workflows.remove_workflow,
        name="remove",
    ),
    path(
        "tasks/add/<slug:app_label>/<slug:model_name>/",
        workflows.CreateTask.as_view(),
        name="add_task",
    ),
    path("tasks/select_type/", workflows.select_task_type, name="select_task_type"),
    path("tasks/index/", workflows.TaskIndex.as_view(), name="task_index"),
    path(
        "tasks/index/results/",
        workflows.TaskIndex.as_view(results_only=True),
        name="task_index_results",
    ),
    path("tasks/edit/<object_id:pk>/", workflows.EditTask.as_view(), name="edit_task"),
    path(
        "tasks/disable/<object_id:pk>/",
        workflows.DisableTask.as_view(),
        name="disable_task",
    ),
    path("tasks/enable/<object_id:pk>/", workflows.enable_task, name="enable_task"),
    path("task_chooser/", workflows.TaskChooserView.as_view(), name="task_chooser"),
    path(
        "task_chooser/results/",
        workflows.TaskChooserResultsView.as_view(),
        name="task_chooser_results",
    ),
    path(
        "task_chooser/create/",
        workflows.TaskChooserCreateView.as_view(),
        name="task_chooser_create",
    ),
    path(
        "task_chooser/<object_id:task_id>/", workflows.task_chosen, name="task_chosen"
    ),
]
