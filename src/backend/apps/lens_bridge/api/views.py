from django.http import JsonResponse, StreamingHttpResponse
import uuid

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.iam.permissions_org import IsOrgOperator, IsOrgStaffReader, IsOrgWriter
from apps.lens_bridge.api.serializers import (
    LensChatBindingEnsureSerializer,
    LensCopilotGatewayOptionSerializer,
    LensGatewayEnableAiSerializer,
    LensKnowledgeSourceCreateSerializer,
    LensKnowledgeSourceSerializer,
    LensKnowledgeSourceUpdateSerializer,
    LensOrgSettingsSerializer,
    LensRunCreateSerializer,
    LensSessionCreateSerializer,
    LensSessionLinkSerializer,
    LensSessionTitleSerializer,
    LensSessionUpdateSerializer,
)
from apps.lens_bridge.models import LensGatewayLink, LensKnowledgeSource, LensSessionLink
from apps.lens_bridge.services import knowledge_source_sync, org_models, provisioning, sl_client, usage
from apps.iam.permissions_org import get_membership
from apps.lens_bridge.services import assistant_access, chat_binding as chat_binding_service, copilot as copilot_service
from apps.lens_bridge.services.assistants import (
    assistant_form_options,
    create_org_assistant,
    delete_org_assistant,
    get_org_assistant,
    list_org_assistants,
    update_org_assistant,
)
from apps.lens_bridge.services.org_mcp_servers import (
    create_org_mcp_server,
    delete_org_mcp_server,
    get_org_mcp_server,
    list_org_mcp_servers,
    update_org_mcp_server,
)
from apps.lens_bridge.services.skills import beautify_skill
from apps.lens_bridge.services.org_skills import (
    create_org_skill,
    delete_org_skill,
    get_org_skill,
    list_org_skills,
    update_org_skill,
)
from common.drf.org_scoped import OrgScopedMixin
from common.drf.renderers import ServerSentEventsRenderer


def health(request):
    ping = sl_client.ping()
    return JsonResponse({"app": "lens_bridge", "status": "ok", "lens": ping})


class LensModelProxyView(OrgScopedMixin, APIView):
    """Proxy SourceLens LLM config admin API (organization-scoped ownership)."""

    permission_classes = [IsAuthenticated, IsOrgStaffReader]

    def get_permissions(self):
        if self.request.method not in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticated(), IsOrgWriter()]
        return super().get_permissions()

    def get(self, request, config_uuid=None):
        url_name = getattr(request.resolver_match, "url_name", "")
        if url_name == "lens-models-providers":
            data = sl_client.request_json("GET", "/api/v1/admin/llm-config/providers/")
        elif url_name == "lens-models-catalog":
            data = sl_client.request_json("GET", "/api/v1/admin/llm-config/models/")
        elif config_uuid:
            link = org_models.require_org_model(self.org, config_uuid)
            data = sl_client.request_json("GET", f"/api/v1/admin/llm-config/{config_uuid}/")
            data = org_models.merge_model_display_name(data, link)
        else:
            data = org_models.list_org_model_configs(self.org)
        return Response(data)

    def post(self, request, config_uuid=None):
        url_name = getattr(request.resolver_match, "url_name", "")
        if url_name == "lens-models-test":
            data = sl_client.request_json(
                "POST",
                "/api/v1/admin/llm-config/test/",
                json_body=request.data,
            )
            return Response(data)
        if url_name == "lens-models-test-call" and config_uuid:
            org_models.require_org_model(self.org, config_uuid)
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
            link = org_models.register_org_model(
                org=self.org,
                sl_config_uuid=uuid.UUID(str(config_uuid_created)),
                created_by=request.user,
            )
            org_models.set_model_display_name(link, display_name)
            data = org_models.merge_model_display_name(data, link)
        return Response(data, status=status.HTTP_201_CREATED)

    def put(self, request, config_uuid):
        link = org_models.require_org_model(self.org, config_uuid)
        body = dict(request.data)
        display_name = body.pop("name", None)
        data = sl_client.request_json(
            "PUT",
            f"/api/v1/admin/llm-config/{config_uuid}/",
            json_body=body,
        )
        org_models.set_model_display_name(link, display_name)
        return Response(org_models.merge_model_display_name(data, link))

    def patch(self, request, config_uuid):
        """Partial update — SourceLens admin API accepts PUT, not PATCH."""
        link = org_models.require_org_model(self.org, config_uuid)
        body = dict(request.data)
        display_name = body.pop("name", None)
        if body:
            data = sl_client.request_json(
                "PUT",
                f"/api/v1/admin/llm-config/{config_uuid}/",
                json_body=body,
            )
        else:
            data = sl_client.request_json("GET", f"/api/v1/admin/llm-config/{config_uuid}/")
        org_models.set_model_display_name(link, display_name)
        link.refresh_from_db(fields=["display_name"])
        return Response(org_models.merge_model_display_name(data, link))

    def delete(self, request, config_uuid):
        org_models.delete_org_model(self.org, config_uuid)
        return Response(status=status.HTTP_204_NO_CONTENT)


class LensOrgSettingsView(OrgScopedMixin, APIView):
    """Per-organization SourceLens defaults (e.g. default agent model for new Assistants)."""

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticated(), IsOrgStaffReader()]
        return [IsAuthenticated(), IsOrgWriter()]

    def get(self, request):
        link = provisioning.get_or_create_org_link(self.org)
        return Response(
            LensOrgSettingsSerializer(
                {"default_agent_model_ref": link.default_agent_model_ref}
            ).data
        )

    def patch(self, request):
        body = LensOrgSettingsSerializer(data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        link = provisioning.get_or_create_org_link(self.org)
        if "default_agent_model_ref" in body.validated_data:
            ref = body.validated_data["default_agent_model_ref"]
            org_models.validate_default_model_ref(self.org, ref)
            link.default_agent_model_ref = ref
            link.save(update_fields=["default_agent_model_ref", "updated_at"])
        return Response(
            LensOrgSettingsSerializer(
                {"default_agent_model_ref": link.default_agent_model_ref}
            ).data
        )


class LensCopilotReadinessView(OrgScopedMixin, APIView):
    """Return sanitized platform AI models available to Copilot."""

    permission_classes = [IsAuthenticated, IsOrgStaffReader]

    def get(self, request):
        rows = []
        for model in org_models.active_llm_configs(org=self.org):
            config = model.get("config") if isinstance(model.get("config"), dict) else {}
            rows.append(
                {
                    "uuid": str(model["uuid"]),
                    "name": str(model.get("name") or ""),
                    "provider": str(model.get("provider") or ""),
                    "config": {"model": str(config.get("model") or "")},
                    "is_active": True,
                }
            )
        return Response({"active_models": rows})


class LensKnowledgeSourceViewSet(OrgScopedMixin, viewsets.ModelViewSet):
    queryset = LensKnowledgeSource.objects.select_related("gateway").all()
    permission_classes = [IsAuthenticated, IsOrgWriter]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated(), IsOrgStaffReader()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "create":
            return LensKnowledgeSourceCreateSerializer
        if self.action in ("update", "partial_update"):
            return LensKnowledgeSourceUpdateSerializer
        return LensKnowledgeSourceSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["org"] = self.org
        return ctx

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        for ks in queryset:
            knowledge_source_sync.maybe_refresh_degraded_status(ks=ks)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        ks = self.get_object()
        knowledge_source_sync.maybe_refresh_degraded_status(ks=ks)
        serializer = self.get_serializer(ks)
        return Response(serializer.data)

    def perform_create(self, serializer):
        gateway = provisioning.require_gateway_node(self.org, serializer.validated_data["gateway"].id)
        gateway_link = provisioning.get_gateway_link(self.org, gateway.id)
        ks = serializer.save(
            organization=self.org,
            created_by=self.request.user,
            sl_lensnode_uuid=gateway_link.sl_lensnode_uuid,
        )
        ks = knowledge_source_sync.prepare_new_knowledge_source(org=self.org, ks=ks)
        knowledge_source_sync.enqueue_knowledge_source_sync(
            organization_id=self.org.id,
            knowledge_source_id=ks.id,
            mode="full",
        )

    def perform_update(self, serializer):
        scan_changed = "scan_enabled" in serializer.validated_data
        ks = serializer.save()
        if scan_changed and not ks.scan_enabled:
            ks.status = LensKnowledgeSource.Status.PAUSED
            ks.save(update_fields=["status", "updated_at"])

    @action(detail=True, methods=["post"])
    def sync(self, request, pk=None):
        ks = self.get_object()
        try:
            ks = knowledge_source_sync.request_knowledge_source_sync(
                org=self.org,
                ks=ks,
                mode="resume",
            )
        except Exception as exc:
            from rest_framework.exceptions import ValidationError as DRFValidationError

            if isinstance(exc, DRFValidationError):
                raise
            ks.status = LensKnowledgeSource.Status.ERROR
            ks.status_detail = str(exc)
            ks.save(update_fields=["status", "status_detail", "updated_at"])
            raise
        return Response(
            LensKnowledgeSourceSerializer(ks, context=self.get_serializer_context()).data
        )


class LensGatewayViewSet(OrgScopedMixin, viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsOrgStaffReader]

    def get_permissions(self):
        if self.action in ("enable_ai", "ai_status"):
            return [IsAuthenticated(), IsOrgWriter()]
        return super().get_permissions()

    def list(self, request):
        from apps.lens_bridge.services.gateway_insights import list_user_gateway_insight_rows

        return Response(list_user_gateway_insight_rows(user=request.user))

    @action(detail=True, methods=["post"], url_path="enable-ai")
    def enable_ai(self, request, pk=None):
        gateway = provisioning.require_gateway_node(self.org, int(pk))
        body = LensGatewayEnableAiSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        link = LensGatewayLink.objects.filter(
            organization=self.org,
            gateway=gateway,
            scope=LensGatewayLink.GatewayScope.USER,
        ).first()
        if link and link.sl_lensnode_uuid:
            provisioning.sync_gateway_lensnode_status(link)
        link = provisioning.enable_ai_on_gateway(
            org=self.org,
            gateway=gateway,
            name=body.validated_data.get("name") or None,
            scope=LensGatewayLink.GatewayScope.USER,
        )
        payload = provisioning.build_gateway_ai_payload(
            gateway=gateway,
            link=link,
            include_token=True,
        )
        return Response(payload, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="ai")
    def ai_status(self, request, pk=None):
        gateway = provisioning.require_gateway_node(self.org, int(pk))
        link = LensGatewayLink.objects.filter(
            organization=self.org,
            gateway=gateway,
            scope=LensGatewayLink.GatewayScope.USER,
        ).first()
        if link and link.sl_lensnode_uuid:
            provisioning.sync_gateway_lensnode_status(link)
        return Response(
            provisioning.build_gateway_ai_payload(
                gateway=gateway,
                link=link,
                include_token=False,
            )
        )

    @action(detail=True, methods=["get"], url_path="browse")
    def browse(self, request, pk=None):
        path = str(request.query_params.get("path") or "").strip()
        try:
            data = provisioning.browse_gateway_directory(
                org=self.org,
                gateway_id=int(pk),
                path=path,
            )
        except ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(data)


class LensCopilotBindingView(OrgScopedMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgStaffReader]

    def get_permissions(self):
        if self.request.method in ("POST",):
            return [IsAuthenticated(), IsOrgOperator()]
        return super().get_permissions()

    def get(self, request):
        binding = chat_binding_service.get_active_chat_binding(self.org, user=request.user)
        if binding is None:
            return Response({"binding": None})
        return Response(
            {"binding": chat_binding_service.serialize_chat_binding(binding)},
        )

    def post(self, request):
        body = LensChatBindingEnsureSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            binding = chat_binding_service.ensure_chat_binding(
                self.org,
                user=request.user,
                backup_config_id=body.validated_data["backup_config_id"],
                backup_source_snapshot_id=body.validated_data["backup_source_snapshot_id"],
                backup_snapshot_directory_id=body.validated_data.get("backup_snapshot_directory_id"),
                source_path=body.validated_data.get("source_path") or "",
                gateway_link_id=body.validated_data.get("gateway_link_id"),
            )
        except ValidationError:
            raise
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(
            {"binding": chat_binding_service.serialize_chat_binding(binding)},
            status=status.HTTP_201_CREATED,
        )


class LensCopilotGatewayOptionsView(OrgScopedMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgStaffReader]

    def get(self, request):
        rows = chat_binding_service.list_gateway_options(self.org, user=request.user)
        return Response(LensCopilotGatewayOptionSerializer(rows, many=True).data)


class LensCopilotAssistantView(OrgScopedMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgStaffReader]

    def get(self, request):
        membership = get_membership(request)
        try:
            rows = copilot_service.list_copilot_assistants(
                self.org,
                user=request.user,
                membership=membership,
            )
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(rows)


class LensCopilotKnowledgeSourceView(OrgScopedMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgStaffReader]

    def get(self, request):
        qs = LensKnowledgeSource.objects.filter(
            organization=self.org,
            scan_enabled=True,
            status__in=[
                LensKnowledgeSource.Status.READY,
                LensKnowledgeSource.Status.DEGRADED,
            ],
        ).select_related("gateway")
        return Response(
            LensKnowledgeSourceSerializer(qs, many=True, context={"view": self}).data
        )



class LensAssistantViewSet(OrgScopedMixin, viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsOrgStaffReader]

    def get_permissions(self):
        if self.action in ("create", "partial_update", "destroy"):
            return [IsAuthenticated(), IsOrgWriter()]
        return super().get_permissions()

    def list(self, request):
        membership = get_membership(request)
        manage = assistant_access.can_manage_all_assistants(membership)
        try:
            rows = list_org_assistants(
                self.org,
                user=request.user,
                membership=membership,
                manage=manage,
            )
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(rows)

    def retrieve(self, request, pk=None):
        membership = get_membership(request)
        manage = assistant_access.can_manage_all_assistants(membership)
        try:
            data = get_org_assistant(
                self.org,
                uuid.UUID(str(pk)),
                user=request.user,
                membership=membership,
                manage=manage,
            )
        except NotFound:
            raise
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(data)

    def create(self, request):
        try:
            data = create_org_assistant(self.org, dict(request.data), user=request.user)
        except ValidationError:
            raise
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        try:
            data = update_org_assistant(
                self.org,
                uuid.UUID(str(pk)),
                dict(request.data),
                user=request.user,
            )
        except NotFound:
            raise
        except ValidationError:
            raise
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(data)

    def destroy(self, request, pk=None):
        try:
            delete_org_assistant(self.org, uuid.UUID(str(pk)))
        except NotFound:
            raise
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="form-options")
    def form_options(self, request):
        try:
            data = assistant_form_options(self.org)
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(data)


class LensSkillViewSet(OrgScopedMixin, viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsOrgStaffReader]

    def get_permissions(self):
        if self.action in ("create", "partial_update", "destroy", "beautify"):
            return [IsAuthenticated(), IsOrgWriter()]
        return super().get_permissions()

    def list(self, request):
        try:
            rows = list_org_skills(self.org)
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(rows)

    def retrieve(self, request, pk=None):
        try:
            data = get_org_skill(self.org, uuid.UUID(str(pk)))
        except NotFound:
            raise
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(data)

    def create(self, request):
        try:
            data = create_org_skill(self.org, dict(request.data), created_by=request.user)
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        try:
            data = update_org_skill(self.org, uuid.UUID(str(pk)), dict(request.data))
        except NotFound:
            raise
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(data)

    def destroy(self, request, pk=None):
        try:
            delete_org_skill(self.org, uuid.UUID(str(pk)))
        except NotFound:
            raise
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="beautify")
    def beautify(self, request):
        try:
            data = beautify_skill(dict(request.data))
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(data)


class LensMcpServerViewSet(OrgScopedMixin, viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsOrgStaffReader]

    def get_permissions(self):
        if self.action in ("create", "partial_update", "destroy"):
            return [IsAuthenticated(), IsOrgWriter()]
        return super().get_permissions()

    def list(self, request):
        try:
            rows = list_org_mcp_servers(self.org)
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(rows)

    def retrieve(self, request, pk=None):
        try:
            data = get_org_mcp_server(self.org, uuid.UUID(str(pk)))
        except NotFound:
            raise
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(data)

    def create(self, request):
        try:
            data = create_org_mcp_server(self.org, dict(request.data), created_by=request.user)
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        try:
            data = update_org_mcp_server(self.org, uuid.UUID(str(pk)), dict(request.data))
        except NotFound:
            raise
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(data)

    def destroy(self, request, pk=None):
        try:
            delete_org_mcp_server(self.org, uuid.UUID(str(pk)))
        except NotFound:
            raise
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(status=status.HTTP_204_NO_CONTENT)


class LensCopilotSessionViewSet(OrgScopedMixin, viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsOrgStaffReader]

    def get_permissions(self):
        if self.action in (
            "create",
            "destroy",
            "create_run",
            "set_model",
            "set_title",
            "mark_viewed",
            "cancel_run",
            "retry",
        ):
            return [IsAuthenticated(), IsOrgOperator()]
        return super().get_permissions()

    def _user_sessions(self):
        return LensSessionLink.objects.filter(
            organization=self.org,
            hfl_user=self.request.user,
            status=LensSessionLink.Status.ACTIVE,
        ).select_related("knowledge_source", "gateway_link__gateway")

    def list(self, request):
        rows = self._user_sessions().order_by("-last_message_at", "-created_at")
        membership = get_membership(request)
        assistant_meta: dict[str, dict[str, str]] = {}
        try:
            for row in copilot_service.list_copilot_assistants(
                self.org,
                user=request.user,
                membership=membership,
            ):
                uuid_str = str(row.get("uuid") or "")
                if uuid_str:
                    assistant_meta[uuid_str] = {
                        "name": str(row.get("name") or ""),
                        "task": str(row.get("selected_task") or ""),
                    }
        except sl_client.LensBridgeError:
            assistant_meta = {}
        context = {
            "assistant_names": {k: v["name"] for k, v in assistant_meta.items()},
            "assistant_tasks": {k: v["task"] for k, v in assistant_meta.items()},
        }
        return Response(
            LensSessionLinkSerializer(rows, many=True, context=context).data,
        )

    def create(self, request):
        body = LensSessionCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            from apps.lens_bridge.services import chat_lifecycle

            link = chat_lifecycle.create_copilot_chat(
                self.org,
                user=request.user,
                backup_config_id=body.validated_data["backup_config_id"],
                backup_source_snapshot_id=body.validated_data["backup_source_snapshot_id"],
                source_scopes=body.validated_data["source_scopes"],
                gateway_mode=body.validated_data["gateway_mode"],
                gateway_link_id=body.validated_data.get("gateway_link_id"),
                title=body.validated_data.get("title"),
            )
        except ValidationError:
            raise
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(LensSessionLinkSerializer(link).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path="model")
    def set_model(self, request, pk=None):
        link = self._get_user_link(pk)
        body = LensSessionUpdateSerializer(data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        model_ref = body.validated_data.get("agent_model_ref")
        if model_ref is None:
            return Response(LensSessionLinkSerializer(link).data)
        org_models.validate_default_model_ref(self.org, model_ref)
        ks = link.knowledge_source
        if ks is None:
            return Response(
                {"agent_model_ref": "Knowledge source is not ready."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        provisioning.sync_assistant_agent_model(
            ks=ks,
            model_ref=model_ref,
            assistant_uuid=link.sl_assistant_uuid,
        )
        link.agent_model_ref = model_ref
        link.save(update_fields=["agent_model_ref", "updated_at"])
        return Response(LensSessionLinkSerializer(link).data)

    @action(detail=True, methods=["patch"], url_path="title")
    def set_title(self, request, pk=None):
        link = self._get_user_link(pk)
        body = LensSessionTitleSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        title = body.validated_data["title"]
        if link.sl_session_uuid:
            self._require_ready_session(link)
            sl_client.request_json(
                "PATCH",
                f"/api/lens/sessions/{link.sl_session_uuid}/",
                json_body={"title": title},
                hfl_user=request.user,
            )
        link.title = title
        link.save(update_fields=["title", "updated_at"])
        return Response(LensSessionLinkSerializer(link).data)

    @action(detail=True, methods=["post"], url_path="viewed")
    def mark_viewed(self, request, pk=None):
        from django.utils import timezone

        link = self._get_user_link(pk)
        link.last_viewed_at = timezone.now()
        link.save(update_fields=["last_viewed_at", "updated_at"])
        return Response(LensSessionLinkSerializer(link).data)

    def retrieve(self, request, pk=None):
        link = self._get_user_link(pk)
        return Response(LensSessionLinkSerializer(link).data)

    def destroy(self, request, pk=None):
        link = self._get_user_link(pk)
        from apps.lens_bridge.services import chat_lifecycle

        chat_lifecycle.request_copilot_chat_teardown(link)
        return Response(LensSessionLinkSerializer(link).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"], url_path="retry")
    def retry(self, request, pk=None):
        link = self._get_user_link(pk)
        from apps.lens_bridge.services import chat_lifecycle

        link = chat_lifecycle.retry_copilot_chat_provision(link)
        link.refresh_from_db()
        return Response(LensSessionLinkSerializer(link).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["get"], url_path="messages")
    def messages(self, request, pk=None):
        link = self._get_user_link(pk)
        if link.lifecycle_status != LensSessionLink.LifecycleStatus.READY or not link.sl_session_uuid:
            return Response([])
        data = sl_client.request_json(
            "GET",
            f"/api/lens/sessions/{link.sl_session_uuid}/messages/",
            hfl_user=request.user,
        )
        return Response(data)

    @action(detail=True, methods=["post"], url_path="runs")
    def create_run(self, request, pk=None):
        link = self._get_user_link(pk)
        self._require_ready_session(link)
        body = LensRunCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        payload = {"question": body.validated_data.get("question") or ""}
        if body.validated_data.get("idempotency_key"):
            payload["idempotency_key"] = body.validated_data["idempotency_key"]
        data = sl_client.request_json(
            "POST",
            f"/api/lens/sessions/{link.sl_session_uuid}/runs/",
            json_body=payload,
            hfl_user=request.user,
        )
        from django.utils import timezone

        link.last_message_at = timezone.now()
        run_uuid = data.get("uuid")
        run_status = str(data.get("status") or "queued")
        if run_uuid:
            link.save(update_fields=["last_message_at", "updated_at"])
            copilot_service.set_active_run(
                link,
                run_uuid=uuid.UUID(str(run_uuid)),
                status=run_status,
            )
            usage.register_usage_run(
                link,
                run_uuid=uuid.UUID(str(run_uuid)),
                question=payload["question"],
                status=run_status,
            )
        else:
            link.save(update_fields=["last_message_at", "updated_at"])
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="sync")
    def sync(self, request, pk=None):
        link = self._get_user_link(pk)
        if link.lifecycle_status != LensSessionLink.LifecycleStatus.READY or not link.sl_session_uuid:
            return Response(
                {
                    "session_id": link.id,
                    "messages": [],
                    "active_run": None,
                    "lifecycle_status": link.lifecycle_status,
                    "lifecycle_error": link.lifecycle_error,
                }
            )
        try:
            data = copilot_service.sync_copilot_session(link)
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        data["lifecycle_status"] = link.lifecycle_status
        data["lifecycle_error"] = link.lifecycle_error
        data["last_assistant_message_at"] = link.last_assistant_message_at
        data["has_unread"] = bool(
            link.last_assistant_message_at
            and (
                link.last_viewed_at is None
                or link.last_assistant_message_at > link.last_viewed_at
            )
        )
        return Response(data)


    @action(detail=True, methods=["get"], url_path="active-run")
    def active_run(self, request, pk=None):
        link = self._get_user_link(pk)
        try:
            payload = copilot_service.get_active_run_payload(link)
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"active_run": payload})

    @action(
        detail=True,
        methods=["post"],
        url_path=r"runs/(?P<run_uuid>[^/.]+)/cancel",
    )
    def cancel_run(self, request, pk=None, run_uuid=None):
        link = self._get_user_link(pk)
        try:
            data = copilot_service.cancel_copilot_run(link, uuid.UUID(str(run_uuid)))
        except ValidationError:
            raise
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(data)

    def _get_user_link(self, pk) -> LensSessionLink:
        link = self._user_sessions().filter(pk=pk).first()
        if link is None:
            from rest_framework.exceptions import NotFound

            raise NotFound()
        return link

    def _require_ready_session(self, link: LensSessionLink) -> None:
        if link.lifecycle_status != LensSessionLink.LifecycleStatus.READY or not link.sl_session_uuid:
            raise ValidationError(
                {
                    "lifecycle_status": (
                        link.lifecycle_error
                        or "Chat is still preparing. Please wait until provisioning finishes."
                    )
                }
            )


class LensCopilotUsageView(OrgScopedMixin, APIView):
    """Current user's HFL-contextualized SourceLens usage and Q&A costs."""

    permission_classes = [IsAuthenticated, IsOrgStaffReader]

    def get(self, request, run_uuid=None):
        try:
            if run_uuid is not None:
                return Response(usage.usage_detail(self.org, request.user, run_uuid))
            return Response(usage.usage_overview(self.org, request.user, request.query_params))
        except sl_client.LensBridgeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


class LensCopilotRunStreamView(APIView):
    permission_classes = [IsAuthenticated, IsOrgOperator]
    renderer_classes = [ServerSentEventsRenderer]

    def get(self, request, run_uuid, session_id=None):
        from apps.iam.org_context import require_org
        from rest_framework.exceptions import NotFound

        org = require_org(request)
        qs = LensSessionLink.objects.filter(
            organization=org,
            hfl_user=request.user,
            status=LensSessionLink.Status.ACTIVE,
        )
        if session_id is not None:
            link = qs.filter(pk=session_id).first()
        else:
            link = qs.first()
        if link is None:
            raise NotFound()

        stream = sl_client.stream_sse(
            f"/api/lens/runs/{run_uuid}/stream/",
            hfl_user=request.user,
        )
        response = StreamingHttpResponse(stream, content_type="text/event-stream; charset=utf-8")
        response["Cache-Control"] = "no-cache, no-transform"
        response["X-Accel-Buffering"] = "no"
        response["Connection"] = "keep-alive"
        return response
