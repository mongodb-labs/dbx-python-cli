# Copied from wagtail/admin/urls/pages.py (Wagtail 7.3.1)
# <int: path converters replaced with <object_id: for Django MongoDB Backend compatibility.
# The revisions_compare re_path regex \d+ replaced with [0-9a-fA-F]{24} to match ObjectIDs.
# Re-diff against upstream on Wagtail upgrades.
from django.urls import path, re_path

from wagtail.admin.views import page_privacy
from wagtail.admin.views.pages import (
    convert_alias,
    copy,
    create,
    delete,
    edit,
    history,
    lock,
    move,
    ordering,
    preview,
    revisions,
    search,
    unpublish,
    usage,
    workflow,
)

app_name = "wagtailadmin_pages"
urlpatterns = [
    path(
        "add/<slug:content_type_app_name>/<slug:content_type_model_name>/<object_id:parent_page_id>/",
        create.CreateView.as_view(),
        name="add",
    ),
    path(
        "add/<slug:content_type_app_name>/<slug:content_type_model_name>/<object_id:parent_page_id>/preview/",
        preview.PreviewOnCreate.as_view(),
        name="preview_on_add",
    ),
    path(
        "usage/<slug:content_type_app_name>/<slug:content_type_model_name>/",
        usage.ContentTypeUseView.as_view(),
        name="type_use",
    ),
    path(
        "usage/<slug:content_type_app_name>/<slug:content_type_model_name>/results/",
        usage.ContentTypeUseView.as_view(results_only=True),
        name="type_use_results",
    ),
    path("<object_id:page_id>/usage/", usage.UsageView.as_view(), name="usage"),
    path("<object_id:page_id>/edit/", edit.EditView.as_view(), name="edit"),
    path(
        "<object_id:page_id>/edit/preview/",
        preview.PreviewOnEdit.as_view(),
        name="preview_on_edit",
    ),
    path("<object_id:page_id>/view_draft/", preview.view_draft, name="view_draft"),
    path(
        "<object_id:parent_page_id>/add_subpage/",
        create.add_subpage,
        name="add_subpage",
    ),
    path("<object_id:page_id>/delete/", delete.delete, name="delete"),
    path(
        "<object_id:page_id>/unpublish/",
        unpublish.Unpublish.as_view(),
        name="unpublish",
    ),
    path(
        "<object_id:page_id>/convert_alias/",
        convert_alias.convert_alias,
        name="convert_alias",
    ),
    path("search/", search.SearchView.as_view(), name="search"),
    path(
        "search/results/",
        search.SearchView.as_view(results_only=True),
        name="search_results",
    ),
    path(
        "<object_id:page_to_move_id>/move/",
        move.MoveChooseDestination.as_view(),
        name="move",
    ),
    path(
        "<object_id:page_to_move_id>/move/<object_id:destination_id>/confirm/",
        move.move_confirm,
        name="move_confirm",
    ),
    # re_path instead of <object_id:> so that Wagtail's reverse("...set_page_position",
    # args=[999999]) sentinel probe succeeds — the view's ORM query coerces the string to ObjectId.
    re_path(
        r"^(?P<page_to_move_id>[0-9a-fA-F]{24}|\d+)/set_position/$",
        ordering.set_page_position,
        name="set_page_position",
    ),
    path("<object_id:page_id>/copy/", copy.copy, name="copy"),
    path(
        "workflow/action/<object_id:page_id>/<slug:action_name>/<object_id:task_state_id>/",
        workflow.WorkflowAction.as_view(),
        name="workflow_action",
    ),
    path(
        "workflow/collect_action_data/<object_id:page_id>/<slug:action_name>/<object_id:task_state_id>/",
        workflow.CollectWorkflowActionData.as_view(),
        name="collect_workflow_action_data",
    ),
    path(
        "workflow/confirm_cancellation/<object_id:page_id>/",
        workflow.ConfirmWorkflowCancellation.as_view(),
        name="confirm_workflow_cancellation",
    ),
    path(
        "workflow/preview/<object_id:page_id>/<object_id:task_id>/",
        workflow.PreviewRevisionForTask.as_view(),
        name="workflow_preview",
    ),
    path("<object_id:page_id>/privacy/", page_privacy.set_privacy, name="set_privacy"),
    path("<object_id:page_id>/lock/", lock.LockView.as_view(), name="lock"),
    path("<object_id:page_id>/unlock/", lock.UnlockView.as_view(), name="unlock"),
    path(
        "<object_id:page_id>/revisions/",
        revisions.revisions_index,
        name="revisions_index",
    ),
    path(
        "<object_id:page_id>/revisions/<object_id:revision_id>/view/",
        revisions.RevisionsView.as_view(),
        name="revisions_view",
    ),
    path(
        "<object_id:page_id>/revisions/<object_id:revision_id>/revert/",
        revisions.RevisionsRevertView.as_view(),
        name="revisions_revert",
    ),
    path(
        "<object_id:page_id>/revisions/<object_id:revision_id>/unschedule/",
        revisions.RevisionsUnschedule.as_view(),
        name="revisions_unschedule",
    ),
    re_path(
        r"^([0-9a-fA-F]{24})/revisions/compare/(live|earliest|[0-9a-fA-F]{24})\.\.\.(live|latest|[0-9a-fA-F]{24})/$",
        revisions.RevisionsCompare.as_view(),
        name="revisions_compare",
    ),
    path(
        "<object_id:page_id>/workflow_history/",
        history.WorkflowHistoryView.as_view(),
        name="workflow_history",
    ),
    path(
        "<object_id:page_id>/workflow_history/detail/<object_id:workflow_state_id>/",
        history.WorkflowHistoryDetailView.as_view(),
        name="workflow_history_detail",
    ),
    path(
        "<object_id:page_id>/history/",
        history.PageHistoryView.as_view(),
        name="history",
    ),
    path(
        "<object_id:page_id>/history/results/",
        history.PageHistoryView.as_view(results_only=True),
        name="history_results",
    ),
]
