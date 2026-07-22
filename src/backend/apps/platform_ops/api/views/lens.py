"""Platform-scoped SourceLens management (Admin Console Engine)."""

from __future__ import annotations

import uuid

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services.interface import write_audit_log
from apps.lens_bridge.api.serializers import (
    LensGatewayEnableAiSerializer,
    LensKnowledgeSourceCreateSerializer,
    LensKnowledgeSourceSerializer,
    LensKnowledgeSourceUpdateSerializer,
)
from apps.iam.models import Organization
from apps.lens_bridge.models import (
    LensGatewayLink,
    LensKnowledgeSource,
    LensOrgModelLink,
)
from apps.lens_bridge.services import (
    gateway_readiness,
    knowledge_source_sync,
    org_models,
    platform_lens,
    provisioning,
    sl_client,
)
from apps.lens_bridge.services.assistants import (
    assistant_form_options,
    create_org_assistant,
    delete_org_assistant,
    get_org_assistant,
    list_org_assistants,
    update_org_assistant,
)
from apps.lens_bridge.services.gateway_insights import list_admin_gateway_insight_rows
from apps.lens_bridge.services import mcp_servers as mcp_servers_service
from apps.lens_bridge.services import skills as skills_service
from apps.lens_bridge.services.skills import beautify_skill
from apps.node.api.serializers.lifecycle_watch import (
    NodeLifecycleWatchEntrySerializer,
    NodeLifecycleWatchRequestSerializer,
)
from apps.node.api.serializers.node_operation import (
    NodeOperationBatchPreviewSerializer,
    NodeOperationBatchStartSerializer,
    NodeOperationStartSerializer,
)
from apps.node.api.views.node_operation import _lifecycle_error_response
from apps.node.models import Node, NodeToken
from apps.node.models.base import NodeRole
from apps.node.services.internal.node_lifecycle import (
    LIFECYCLE_KIND_UPGRADE,
    preview_batch_operations,
    start_node_remove,
    start_node_upgrade,
)
from apps.node.services.internal.local_platform_gateway import platform_gateway_api_base
from apps.platform_ops.api.permissions import IsPlatformOpsStaff
from common.deploy.site import enrollment_tls_verify


def _platform_org():
    return platform_lens.get_or_create_platform_org()


def _deployment_managed_model_link(
    org: Organization,
    config_uuid: uuid.UUID,
) -> LensOrgModelLink | None:
    return (
        org_models.org_model_links(org)
        .filter(sl_config_uuid=config_uuid)
        .exclude(management_key="")
        .first()
    )


def _deployment_managed_model_error() -> Response:
    return Response(
        {
            "code": "AI_MODEL_MANAGED_BY_DEPLOYMENT",
            "detail": (
                "This AI model is managed by deployment configuration. "
                "Connection settings are read-only."
            ),
        },
        status=status.HTTP_409_CONFLICT,
    )


def _set_platform_default_model_ref(
    org: Organization,
    config_uuid: uuid.UUID | None,
) -> None:
    link = provisioning.get_or_create_org_link(org)
    if link.default_agent_model_ref == config_uuid:
        return
    link.default_agent_model_ref = config_uuid
    link.save(update_fields=["default_agent_model_ref", "updated_at"])


def _platform_gateway(gateway_id: int) -> Node | None:
    """Return an active HFL Gateway owned by the hidden platform organization."""
    return Node.objects.filter(
        organization=_platform_org(),
        role=NodeRole.GATEWAY,
        pk=int(gateway_id),
    ).first()


def _preview_platform_gateway_operations(*, node_ids: list[int], kind: str) -> dict:
    """Preview only Gateway nodes from the hidden platform organization."""
    org = _platform_org()
    gateway_ids = set(
        Node.objects.filter(
            organization=org,
            role=NodeRole.GATEWAY,
            pk__in=node_ids,
        ).values_list("id", flat=True)
    )
    preview = preview_batch_operations(
        org=org,
        node_ids=[node_id for node_id in node_ids if node_id in gateway_ids],
        kind=kind,
    )
    preview["requested"] = len(node_ids)
    preview["missing_node_ids"] = [
        node_id for node_id in node_ids if node_id not in gateway_ids
    ]
    return preview


def _start_platform_gateway_operation(
    *,
    request: Request,
    gateway: Node,
    kind: str,
    force: bool = False,
) -> dict:
    """Start one platform Gateway lifecycle operation through the shared service."""
    org = _platform_org()
    if kind == LIFECYCLE_KIND_UPGRADE:
        result = start_node_upgrade(org=org, node=gateway, user=request.user)
    else:
        result = start_node_remove(
            org=org,
            node=gateway,
            user=request.user,
            force=force,
        )
    write_audit_log(
        organization=org,
        user=request.user,
        action=f"node.lifecycle.{kind}",
        target_type="node",
        target_id=str(gateway.id),
        ip_address=request.META.get("REMOTE_ADDR"),
        user_agent=str(request.META.get("HTTP_USER_AGENT", "") or ""),
        metadata={
            "kind": kind,
            "role": gateway.role,
            "operation_id": result.get("operation_id"),
            "task_id": result.get("task_id"),
            "state": result.get("state"),
            "scope": "platform",
        },
    )
    return result


class PlatformOpsLensGatewayListView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        return Response(list_admin_gateway_insight_rows(user=request.user))


class PlatformOpsLensGatewayEnrollmentView(APIView):
    """Issue an HFL enrollment token for a platform-owned data gateway."""

    permission_classes = [IsPlatformOpsStaff]

    def post(self, request):
        try:
            api_base = platform_gateway_api_base()
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        org = _platform_org()
        token = NodeToken.objects.create(
            organization=org,
            role=NodeRole.GATEWAY,
            note=str(request.data.get("note") or "deploy:platform-gateway")[:200],
            created_by=request.user,
            gateway_scope=LensGatewayLink.GatewayScope.PLATFORM,
        )
        return Response(
            {
                "token": token.token,
                "token_id": token.id,
                "org_key": org.key,
                "gateway_scope": LensGatewayLink.GatewayScope.PLATFORM,
                "api_base": api_base,
                "tls_verify": enrollment_tls_verify(),
            },
            status=status.HTTP_201_CREATED,
        )


class PlatformOpsLensGatewayEnableAiView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def post(self, request, gateway_id: int):
        org = _platform_org()
        gateway = provisioning.require_gateway_node(org, int(gateway_id))
        body = LensGatewayEnableAiSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        link = provisioning.enable_ai_on_gateway(
            org=org,
            gateway=gateway,
            name=body.validated_data.get("name") or None,
            scope=LensGatewayLink.GatewayScope.PLATFORM,
        )
        payload = provisioning.build_gateway_ai_payload(
            gateway=gateway,
            link=link,
            include_token=True,
        )
        return Response(payload, status=status.HTTP_201_CREATED)


class PlatformOpsLensGatewaySetDefaultView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def post(self, request, gateway_id: int):
        org = _platform_org()
        gateway = provisioning.require_gateway_node(org, int(gateway_id))
        link = LensGatewayLink.objects.filter(
            organization=org,
            gateway=gateway,
            scope=LensGatewayLink.GatewayScope.PLATFORM,
        ).first()
        if link is None or not link.sl_lensnode_uuid:
            return Response(
                {"detail": "Enable AI on this gateway before marking it as platform default."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        gateway_readiness.require_hfl_usable_gateway(link)
        link = platform_lens.set_platform_default_gateway(gateway_link_id=link.id)
        return Response(
            {
                "gateway_link_id": link.id,
                "is_platform_default": link.is_platform_default,
            }
        )


class PlatformOpsLensGatewayOperationView(APIView):
    """Start upgrade/remove for one hidden platform Data Gateway."""

    permission_classes = [IsPlatformOpsStaff]

    def post(self, request, gateway_id: int):
        gateway = _platform_gateway(gateway_id)
        if gateway is None:
            return Response(
                {"detail": "Platform Data Gateway not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        body = NodeOperationStartSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            result = _start_platform_gateway_operation(
                request=request,
                gateway=gateway,
                kind=body.validated_data["kind"],
                force=bool(body.validated_data.get("force")),
            )
        except Exception as exc:
            return _lifecycle_error_response(exc)
        return Response(result, status=status.HTTP_202_ACCEPTED)


class PlatformOpsLensGatewayOperationPreviewView(APIView):
    """Preview lifecycle eligibility for hidden platform Data Gateways."""

    permission_classes = [IsPlatformOpsStaff]

    def post(self, request):
        body = NodeOperationBatchPreviewSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return Response(
            _preview_platform_gateway_operations(
                node_ids=body.validated_data["node_ids"],
                kind=body.validated_data["kind"],
            )
        )


class PlatformOpsLensGatewayOperationBatchView(APIView):
    """Start a bounded batch of hidden platform Gateway lifecycle operations."""

    permission_classes = [IsPlatformOpsStaff]

    def post(self, request):
        body = NodeOperationBatchStartSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        values = body.validated_data
        preview = _preview_platform_gateway_operations(
            node_ids=values["node_ids"],
            kind=values["kind"],
        )
        max_concurrent = int(
            values.get("max_concurrent") or preview.get("max_concurrent") or 5
        )
        eligible = preview.get("eligible") or []
        started: list[dict] = []
        errors: list[dict] = []
        for item in eligible[:max_concurrent]:
            gateway = _platform_gateway(item["node_id"])
            if gateway is None:
                errors.append({"node_id": item["node_id"], "error": "not_found"})
                continue
            try:
                started.append(
                    _start_platform_gateway_operation(
                        request=request,
                        gateway=gateway,
                        kind=values["kind"],
                        force=bool(values.get("force")),
                    )
                )
            except Exception as exc:
                response = _lifecycle_error_response(exc)
                errors.append({"node_id": gateway.id, **response.data})
        return Response(
            {
                **preview,
                "max_concurrent": max_concurrent,
                "started": started,
                "queued": eligible[max_concurrent:],
                "errors": errors,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class PlatformOpsLensGatewayLifecycleWatchView(APIView):
    """Poll lifecycle state for platform Gateway operations."""

    permission_classes = [IsPlatformOpsStaff]

    def post(self, request):
        body = NodeLifecycleWatchRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        org = _platform_org()
        gateways = list(
            Node.objects.filter(
                organization=org,
                role=NodeRole.GATEWAY,
                pk__in=body.validated_data["node_ids"],
            ).order_by("id")
        )
        payload = NodeLifecycleWatchEntrySerializer(
            gateways,
            many=True,
            context={"org": org},
        ).data
        return Response({"nodes": payload})


class PlatformOpsLensModelProxyView(APIView):
    """Admin Console: full SL admin LLM config passthrough (no org-link gate)."""

    permission_classes = [IsPlatformOpsStaff]

    def get(self, request, config_uuid=None):
        org = _platform_org()
        url_name = getattr(request.resolver_match, "url_name", "")
        if url_name == "platform-ops-lens-models-providers":
            data = sl_client.request_json("GET", "/api/v1/admin/llm-config/providers/")
        elif url_name == "platform-ops-lens-models-catalog":
            data = sl_client.request_json("GET", "/api/v1/admin/llm-config/models/")
        elif config_uuid:
            data = sl_client.request_json("GET", f"/api/v1/admin/llm-config/{config_uuid}/")
            link = (
                org_models.org_model_links(org)
                .filter(sl_config_uuid=config_uuid)
                .first()
            )
            data = org_models.merge_model_display_name(data, link)
        else:
            data = org_models.list_all_llm_configs(org=org)
        return Response(data)

    def post(self, request, config_uuid=None):
        org = _platform_org()
        url_name = getattr(request.resolver_match, "url_name", "")
        if url_name == "platform-ops-lens-models-test":
            data = sl_client.request_json(
                "POST",
                "/api/v1/admin/llm-config/test/",
                json_body=request.data,
            )
            return Response(data)
        if url_name == "platform-ops-lens-models-test-call" and config_uuid:
            data = sl_client.request_json(
                "POST",
                f"/api/v1/admin/llm-config/{config_uuid}/test-call/",
                json_body=request.data,
            )
            return Response(data)
        body = dict(request.data)
        display_name = body.pop("name", None)
        data = sl_client.request_json("POST", "/api/v1/admin/llm-config/", json_body=body)
        config_uuid_created = data.get("uuid")
        if config_uuid_created:
            # Keep optional display_name metadata on platform org link.
            link = org_models.register_org_model(
                org=org,
                sl_config_uuid=uuid.UUID(str(config_uuid_created)),
                created_by=request.user,
            )
            org_models.set_model_display_name(link, display_name)
            data = org_models.merge_model_display_name(data, link)
            if body.get("is_default") is True:
                _set_platform_default_model_ref(
                    org,
                    uuid.UUID(str(config_uuid_created)),
                )
        return Response(data, status=status.HTTP_201_CREATED)

    def put(self, request, config_uuid):
        org = _platform_org()
        managed_link = _deployment_managed_model_link(org, config_uuid)
        if managed_link is not None and set(request.data) - {"is_default"}:
            return _deployment_managed_model_error()
        body = dict(request.data)
        display_name = body.pop("name", None)
        data = sl_client.request_json(
            "PUT",
            f"/api/v1/admin/llm-config/{config_uuid}/",
            json_body=body,
        )
        link = (
            org_models.org_model_links(org)
            .filter(sl_config_uuid=config_uuid)
            .first()
        )
        if link is None and display_name is not None:
            link = org_models.register_org_model(
                org=org,
                sl_config_uuid=config_uuid,
                created_by=request.user,
            )
        if link is not None:
            org_models.set_model_display_name(link, display_name)
            link.refresh_from_db(fields=["display_name"])
        if body.get("is_default") is True:
            _set_platform_default_model_ref(org, config_uuid)
        return Response(org_models.merge_model_display_name(data, link))

    def patch(self, request, config_uuid):
        return self.put(request, config_uuid)

    def delete(self, request, config_uuid):
        org = _platform_org()
        if _deployment_managed_model_link(org, config_uuid) is not None:
            return _deployment_managed_model_error()
        sl_client.request_json("DELETE", f"/api/v1/admin/llm-config/{config_uuid}/")
        LensOrgModelLink.objects.filter(
            organization=org,
            sl_config_uuid=config_uuid,
        ).update(is_deleted=True)
        platform_defaults = provisioning.get_or_create_org_link(org)
        if platform_defaults.default_agent_model_ref == config_uuid:
            _set_platform_default_model_ref(org, None)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PlatformOpsLensAssistantView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request, assistant_uuid=None):
        org = _platform_org()
        if assistant_uuid:
            data = get_org_assistant(
                org,
                uuid.UUID(str(assistant_uuid)),
                user=request.user,
                manage=True,
            )
            return Response(data)
        rows = list_org_assistants(org, user=request.user, manage=True)
        return Response(rows)

    def post(self, request):
        org = _platform_org()
        try:
            data = create_org_assistant(org, dict(request.data), user=request.user)
        except ValidationError:
            raise
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(data, status=status.HTTP_201_CREATED)

    def patch(self, request, assistant_uuid):
        org = _platform_org()
        try:
            data = update_org_assistant(
                org,
                uuid.UUID(str(assistant_uuid)),
                dict(request.data),
                user=request.user,
            )
        except ValidationError:
            raise
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(data)

    def delete(self, request, assistant_uuid):
        org = _platform_org()
        delete_org_assistant(org, uuid.UUID(str(assistant_uuid)))
        return Response(status=status.HTTP_204_NO_CONTENT)


class PlatformOpsLensAssistantFormOptionsView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request):
        org = _platform_org()
        # Skills/MCP/models for Admin assistant forms: full SL admin catalogs.
        data = assistant_form_options(org, platform_passthrough=True)
        return Response(data)


class PlatformOpsLensSkillView(APIView):
    """Admin Console: full SL admin skills passthrough."""

    permission_classes = [IsPlatformOpsStaff]

    def get(self, request, skill_uuid=None):
        if skill_uuid:
            return Response(skills_service.get_skill(uuid.UUID(str(skill_uuid))))
        return Response(skills_service.list_skills())

    def post(self, request, skill_uuid=None):
        url_name = getattr(request.resolver_match, "url_name", "")
        if url_name == "platform-ops-lens-skills-beautify":
            return Response(beautify_skill(dict(request.data)))
        data = skills_service.create_skill(dict(request.data))
        return Response(data, status=status.HTTP_201_CREATED)

    def patch(self, request, skill_uuid):
        data = skills_service.update_skill(uuid.UUID(str(skill_uuid)), dict(request.data))
        return Response(data)

    def delete(self, request, skill_uuid):
        skills_service.delete_skill(uuid.UUID(str(skill_uuid)))
        return Response(status=status.HTTP_204_NO_CONTENT)


class PlatformOpsLensMcpServerView(APIView):
    """Admin Console: full SL admin MCP servers passthrough."""

    permission_classes = [IsPlatformOpsStaff]

    def get(self, request, mcp_uuid=None):
        if mcp_uuid:
            return Response(mcp_servers_service.get_mcp_server(uuid.UUID(str(mcp_uuid))))
        return Response(mcp_servers_service.list_mcp_servers())

    def post(self, request):
        data = mcp_servers_service.create_mcp_server(dict(request.data))
        return Response(data, status=status.HTTP_201_CREATED)

    def patch(self, request, mcp_uuid):
        data = mcp_servers_service.update_mcp_server(
            uuid.UUID(str(mcp_uuid)),
            dict(request.data),
        )
        return Response(data)

    def delete(self, request, mcp_uuid):
        mcp_servers_service.delete_mcp_server(uuid.UUID(str(mcp_uuid)))
        return Response(status=status.HTTP_204_NO_CONTENT)


class PlatformOpsLensKnowledgeSourceView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request, ks_id=None):
        org = _platform_org()
        if ks_id is None:
            qs = LensKnowledgeSource.objects.filter(organization=org).select_related("gateway")
            for ks in qs:
                knowledge_source_sync.maybe_refresh_degraded_status(ks=ks)
            data = LensKnowledgeSourceSerializer(qs, many=True, context={"org": org}).data
            return Response(data)
        ks = LensKnowledgeSource.objects.filter(organization=org, pk=ks_id).select_related("gateway").first()
        if ks is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        knowledge_source_sync.maybe_refresh_degraded_status(ks=ks)
        return Response(LensKnowledgeSourceSerializer(ks, context={"org": org}).data)

    def post(self, request):
        org = _platform_org()
        body = LensKnowledgeSourceCreateSerializer(data=request.data, context={"org": org})
        body.is_valid(raise_exception=True)
        gateway = provisioning.require_gateway_node(org, body.validated_data["gateway"].id)
        gateway_link = provisioning.get_gateway_link(org, gateway.id)
        if gateway_link.scope != LensGatewayLink.GatewayScope.PLATFORM:
            gateway_link.scope = LensGatewayLink.GatewayScope.PLATFORM
            gateway_link.save(update_fields=["scope", "updated_at"])
        ks = body.save(
            organization=org,
            created_by=request.user,
            sl_lensnode_uuid=gateway_link.sl_lensnode_uuid,
        )
        ks = knowledge_source_sync.prepare_new_knowledge_source(org=org, ks=ks)
        knowledge_source_sync.enqueue_knowledge_source_sync(
            organization_id=org.id,
            knowledge_source_id=ks.id,
            mode="full",
        )
        return Response(
            LensKnowledgeSourceSerializer(ks, context={"org": org}).data,
            status=status.HTTP_201_CREATED,
        )

    def patch(self, request, ks_id: int):
        org = _platform_org()
        ks = LensKnowledgeSource.objects.filter(organization=org, pk=ks_id).first()
        if ks is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        body = LensKnowledgeSourceUpdateSerializer(ks, data=request.data, partial=True, context={"org": org})
        body.is_valid(raise_exception=True)
        scan_changed = "scan_enabled" in body.validated_data
        ks = body.save()
        if scan_changed and not ks.scan_enabled:
            ks.status = LensKnowledgeSource.Status.PAUSED
            ks.save(update_fields=["status", "updated_at"])
        return Response(LensKnowledgeSourceSerializer(ks, context={"org": org}).data)

    def delete(self, request, ks_id: int):
        org = _platform_org()
        ks = LensKnowledgeSource.objects.filter(organization=org, pk=ks_id).first()
        if ks is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        ks.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PlatformOpsLensKnowledgeSourceSyncView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def post(self, request, ks_id: int):
        org = _platform_org()
        ks = LensKnowledgeSource.objects.filter(organization=org, pk=ks_id).first()
        if ks is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            ks = knowledge_source_sync.request_knowledge_source_sync(
                org=org,
                ks=ks,
                mode="resume",
            )
        except ValidationError:
            raise
        except Exception as exc:
            ks.status = LensKnowledgeSource.Status.ERROR
            ks.status_detail = str(exc)
            ks.save(update_fields=["status", "status_detail", "updated_at"])
            raise
        return Response(LensKnowledgeSourceSerializer(ks, context={"org": org}).data)


class PlatformOpsLensGatewayBrowseView(APIView):
    permission_classes = [IsPlatformOpsStaff]

    def get(self, request, gateway_id: int):
        org = _platform_org()
        path = str(request.query_params.get("path") or "").strip()
        try:
            data = provisioning.browse_gateway_directory(
                org=org,
                gateway_id=int(gateway_id),
                path=path,
            )
        except ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(data)
