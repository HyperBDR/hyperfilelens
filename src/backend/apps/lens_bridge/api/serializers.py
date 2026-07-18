from rest_framework import serializers

from apps.lens_bridge.models import LensKnowledgeSource, LensSessionLink
from apps.lens_bridge.services import gateway_readiness, ingest_policy, provisioning
from apps.protection.models import BackupConfig, BackupSourceSnapshot
from apps.protection.services.source_identity import resolve_source_display_name


class LensKnowledgeSourceSerializer(serializers.ModelSerializer):
    gateway_name = serializers.CharField(source="gateway.name", read_only=True)
    ingest_policy = serializers.SerializerMethodField()
    ingest_summary = serializers.SerializerMethodField()
    sync_phase = serializers.SerializerMethodField()

    class Meta:
        model = LensKnowledgeSource
        fields = [
            "id",
            "name",
            "gateway",
            "gateway_name",
            "backup_source_snapshot_id",
            "backup_snapshot_directory_id",
            "source_path",
            "source_scopes_json",
            "mount_path_on_gateway",
            "workspace_path_on_lensnode",
            "linked_version_mode",
            "pinned_snapshot_id",
            "sl_assistant_uuid",
            "sl_lensnode_uuid",
            "status",
            "status_detail",
            "sync_phase",
            "sync_state_json",
            "last_restore_record_id",
            "ingest_policy",
            "ingest_summary",
            "scan_enabled",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "gateway_name",
            "mount_path_on_gateway",
            "workspace_path_on_lensnode",
            "sl_assistant_uuid",
            "sl_lensnode_uuid",
            "status",
            "status_detail",
            "sync_phase",
            "sync_state_json",
            "last_restore_record_id",
            "ingest_policy",
            "ingest_summary",
            "created_at",
            "updated_at",
        ]

    def _normalized_policy(self, obj: LensKnowledgeSource) -> dict:
        org = getattr(self.context.get("view"), "org", None)
        return ingest_policy.normalize_ingest_policy(obj.ingest_policy_json, org)

    def get_ingest_policy(self, obj: LensKnowledgeSource) -> dict:
        return self._normalized_policy(obj)

    def get_ingest_summary(self, obj: LensKnowledgeSource) -> str:
        return ingest_policy.ingest_summary(self._normalized_policy(obj))

    def get_sync_phase(self, obj: LensKnowledgeSource) -> str:
        sync_state = obj.sync_state_json if isinstance(obj.sync_state_json, dict) else {}
        return str(sync_state.get("phase") or "")


class LensKnowledgeSourceScopeSerializer(serializers.Serializer):
    source_path = serializers.CharField(max_length=1000)
    backup_snapshot_directory_id = serializers.IntegerField(min_value=1)
    path_type = serializers.ChoiceField(
        choices=("dir", "file", "unknown"),
        required=False,
        default="unknown",
    )


class LensKnowledgeSourceCreateSerializer(serializers.ModelSerializer):
    ingest_policy = serializers.JSONField(required=False)
    source_scopes = LensKnowledgeSourceScopeSerializer(many=True, required=False)

    class Meta:
        model = LensKnowledgeSource
        fields = [
            "name",
            "gateway",
            "backup_source_snapshot_id",
            "backup_snapshot_directory_id",
            "source_path",
            "source_scopes",
            "linked_version_mode",
            "pinned_snapshot_id",
            "scan_enabled",
            "ingest_policy",
        ]

    def validate(self, attrs):
        org = self.context.get("org")
        if org is None:
            return attrs
        gateway = attrs["gateway"]
        provisioning.require_gateway_node(org, gateway.id)
        link = provisioning.get_gateway_link(org, gateway.id)
        gateway_readiness.require_hfl_usable_gateway(link, field="gateway")

        source_scopes = attrs.pop("source_scopes", None)
        is_gateway_local = not attrs.get("backup_source_snapshot_id") and not attrs.get(
            "backup_snapshot_directory_id"
        ) and not source_scopes

        if source_scopes:
            normalized_scopes = []
            for index, scope in enumerate(source_scopes):
                path = str(scope.get("source_path") or "").strip()
                directory_id = scope.get("backup_snapshot_directory_id")
                if not path:
                    raise serializers.ValidationError(
                        {"source_scopes": {index: {"source_path": "Source path is required."}}}
                    )
                if not directory_id:
                    raise serializers.ValidationError(
                        {
                            "source_scopes": {
                                index: {
                                    "backup_snapshot_directory_id": "Select a snapshot directory root."
                                }
                            }
                        }
                    )
                normalized_scopes.append(
                    {
                        "source_path": path,
                        "backup_snapshot_directory_id": int(directory_id),
                        "path_type": str(scope.get("path_type") or "unknown"),
                    }
                )
            attrs["source_scopes_json"] = normalized_scopes
            attrs["source_path"] = normalized_scopes[0]["source_path"]
            attrs["backup_snapshot_directory_id"] = normalized_scopes[0][
                "backup_snapshot_directory_id"
            ]
            is_gateway_local = False

        source_path = (attrs.get("source_path") or "").strip()
        if not source_path:
            raise serializers.ValidationError({"source_path": "Source path is required."})
        attrs["source_path"] = source_path

        if is_gateway_local:
            root = link.resolved_workspace_root().rstrip("/") or "/"
            if source_path != root and not source_path.startswith(f"{root}/"):
                raise serializers.ValidationError(
                    {"source_path": "Directory must be under the gateway workspace root."}
                )
        else:
            if not attrs.get("backup_source_snapshot_id"):
                raise serializers.ValidationError(
                    {"backup_source_snapshot_id": "Select a backup snapshot."}
                )
            if not attrs.get("backup_snapshot_directory_id"):
                raise serializers.ValidationError(
                    {"backup_snapshot_directory_id": "Select a snapshot directory root."}
                )

        attrs["ingest_policy_json"] = ingest_policy.normalize_ingest_policy(
            attrs.pop("ingest_policy", None),
            org,
        )
        return attrs


class LensKnowledgeSourceUpdateSerializer(serializers.ModelSerializer):
    ingest_policy = serializers.JSONField(required=False)

    class Meta:
        model = LensKnowledgeSource
        fields = [
            "name",
            "linked_version_mode",
            "pinned_snapshot_id",
            "scan_enabled",
            "ingest_policy",
        ]

    def validate(self, attrs):
        org = self.context.get("org")
        if org is not None and "ingest_policy" in attrs:
            attrs["ingest_policy_json"] = ingest_policy.normalize_ingest_policy(
                attrs.pop("ingest_policy"),
                org,
            )
        mode = attrs.get(
            "linked_version_mode",
            getattr(self.instance, "linked_version_mode", LensKnowledgeSource.LinkedVersionMode.LATEST),
        )
        if mode == LensKnowledgeSource.LinkedVersionMode.PINNED:
            pinned = attrs.get(
                "pinned_snapshot_id",
                getattr(self.instance, "pinned_snapshot_id", None),
            )
            if not pinned:
                raise serializers.ValidationError(
                    {"pinned_snapshot_id": "Pinned snapshot id is required when mode is pinned."}
                )
        return attrs


class SlLensnodeTaskSerializer(serializers.Serializer):
    name = serializers.CharField(allow_blank=True)
    title = serializers.CharField(allow_blank=True)


class LensGatewayInsightSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    role = serializers.CharField()
    status = serializers.CharField()
    ip_address = serializers.IPAddressField(allow_null=True, allow_blank=True, required=False)
    ai_enabled = serializers.BooleanField()
    sl_lensnode_uuid = serializers.UUIDField(allow_null=True)
    lensnode_status = serializers.CharField(allow_null=True)
    knowledge_source_count = serializers.IntegerField()
    workspace_root = serializers.CharField(allow_blank=True)
    sidecar_status = serializers.CharField(allow_blank=True)
    sl_name = serializers.CharField(allow_blank=True, required=False)
    sl_status = serializers.CharField(allow_blank=True, required=False)
    sl_workspace_path = serializers.CharField(allow_blank=True, required=False)
    sl_agent_version = serializers.CharField(allow_blank=True, required=False)
    sl_last_heartbeat_at = serializers.DateTimeField(allow_null=True, required=False)
    sl_registered_at = serializers.DateTimeField(allow_null=True, required=False)
    sl_tasks = SlLensnodeTaskSerializer(many=True, required=False)
    scope = serializers.CharField(required=False, allow_blank=True)
    origin = serializers.CharField(required=False, allow_blank=True)
    gateway_link_id = serializers.IntegerField(required=False, allow_null=True)
    managed_by_hfl = serializers.BooleanField(required=False)
    hfl_agent_online = serializers.BooleanField(required=False)
    hfl_sidecar_online = serializers.BooleanField(required=False)
    hfl_usable = serializers.BooleanField(required=False)
    copilot_eligible = serializers.BooleanField(required=False)
    sl_runtime_status = serializers.CharField(required=False, allow_blank=True)
    owner_user_id = serializers.IntegerField(required=False, allow_null=True)
    owner_username = serializers.CharField(required=False, allow_blank=True)
    owner_organization_id = serializers.IntegerField(required=False, allow_null=True)
    is_platform_default = serializers.BooleanField(required=False)


class LensGatewayEnableAiSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True, max_length=160)


class LensSessionLinkSerializer(serializers.ModelSerializer):
    knowledge_source_name = serializers.CharField(
        source="knowledge_source.name",
        read_only=True,
        allow_null=True,
    )
    assistant_name = serializers.SerializerMethodField()
    selected_task = serializers.SerializerMethodField()
    backup_source_name = serializers.SerializerMethodField()
    snapshot_created_at = serializers.SerializerMethodField()
    snapshot_size_bytes = serializers.SerializerMethodField()
    gateway_name = serializers.SerializerMethodField()
    gateway_scope = serializers.SerializerMethodField()
    has_unread = serializers.SerializerMethodField()

    class Meta:
        model = LensSessionLink
        fields = [
            "id",
            "title",
            "knowledge_source",
            "knowledge_source_name",
            "sl_session_uuid",
            "sl_assistant_uuid",
            "assistant_name",
            "selected_task",
            "agent_model_ref",
            "backup_config_id",
            "backup_source_name",
            "backup_source_snapshot_id",
            "snapshot_created_at",
            "snapshot_size_bytes",
            "source_scopes_json",
            "gateway_link",
            "gateway_selection_mode",
            "gateway_name",
            "gateway_scope",
            "status",
            "lifecycle_status",
            "provision_phase",
            "provision_detail",
            "lifecycle_error",
            "last_message_at",
            "last_assistant_message_at",
            "last_viewed_at",
            "has_unread",
            "active_run_uuid",
            "active_run_status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_assistant_name(self, obj: LensSessionLink) -> str | None:
        cache = self.context.get("assistant_names") or {}
        uuid_str = str(obj.sl_assistant_uuid) if obj.sl_assistant_uuid else ""
        return cache.get(uuid_str)

    def get_selected_task(self, obj: LensSessionLink) -> str | None:
        cache = self.context.get("assistant_tasks") or {}
        uuid_str = str(obj.sl_assistant_uuid) if obj.sl_assistant_uuid else ""
        return cache.get(uuid_str)

    def _backup_config(self, obj: LensSessionLink) -> BackupConfig | None:
        if not obj.backup_config_id:
            return None
        cache = self.context.setdefault("session_backup_configs", {})
        if obj.backup_config_id not in cache:
            cache[obj.backup_config_id] = BackupConfig.objects.filter(
                id=obj.backup_config_id,
                organization_id=obj.organization_id,
            ).first()
        return cache[obj.backup_config_id]

    def _snapshot(self, obj: LensSessionLink) -> BackupSourceSnapshot | None:
        if not obj.backup_source_snapshot_id:
            return None
        cache = self.context.setdefault("session_snapshots", {})
        if obj.backup_source_snapshot_id not in cache:
            cache[obj.backup_source_snapshot_id] = BackupSourceSnapshot.objects.filter(
                id=obj.backup_source_snapshot_id,
                organization_id=obj.organization_id,
            ).first()
        return cache[obj.backup_source_snapshot_id]

    def get_backup_source_name(self, obj: LensSessionLink) -> str | None:
        config = self._backup_config(obj)
        if config is None:
            return None
        cache = self.context.setdefault("session_source_names", {})
        source_key = (obj.organization_id, config.source_type, config.source_ref_id)
        if source_key not in cache:
            cache[source_key] = resolve_source_display_name(
                organization_id=obj.organization_id,
                source_type=config.source_type,
                source_ref_id=config.source_ref_id,
                fallback=config.name,
            )
        return cache[source_key]

    def get_snapshot_created_at(self, obj: LensSessionLink):
        snapshot = self._snapshot(obj)
        if snapshot is None:
            return None
        return snapshot.finished_at or snapshot.started_at or snapshot.created_at

    def get_snapshot_size_bytes(self, obj: LensSessionLink) -> int | None:
        snapshot = self._snapshot(obj)
        return snapshot.total_size_bytes if snapshot else None

    def get_gateway_name(self, obj: LensSessionLink) -> str | None:
        link = obj.gateway_link
        return link.gateway.name if link else None

    def get_gateway_scope(self, obj: LensSessionLink) -> str | None:
        link = obj.gateway_link
        return link.scope if link else None

    def get_has_unread(self, obj: LensSessionLink) -> bool:
        if obj.last_assistant_message_at is None:
            return False
        return obj.last_viewed_at is None or obj.last_assistant_message_at > obj.last_viewed_at


class LensSessionCreateSerializer(serializers.Serializer):
    """New Copilot chat configuration. Resources are provisioned asynchronously."""

    title = serializers.CharField(required=False, allow_blank=True, max_length=160)
    backup_config_id = serializers.IntegerField(min_value=1)
    backup_source_snapshot_id = serializers.IntegerField(min_value=1)
    source_scopes = LensKnowledgeSourceScopeSerializer(many=True, min_length=1)
    gateway_mode = serializers.ChoiceField(
        choices=LensSessionLink.GatewaySelectionMode.choices,
        default=LensSessionLink.GatewaySelectionMode.AUTO,
    )
    gateway_link_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)

    def validate(self, attrs):
        mode = attrs["gateway_mode"]
        gateway_link_id = attrs.get("gateway_link_id")
        if mode == LensSessionLink.GatewaySelectionMode.MANUAL and not gateway_link_id:
            raise serializers.ValidationError(
                {"gateway_link_id": "Select a data gateway when gateway mode is manual."}
            )
        if mode == LensSessionLink.GatewaySelectionMode.AUTO and gateway_link_id is not None:
            raise serializers.ValidationError(
                {"gateway_link_id": "Do not provide a data gateway when gateway mode is auto."}
            )
        return attrs


class LensSessionUpdateSerializer(serializers.Serializer):
    agent_model_ref = serializers.UUIDField(required=False, allow_null=True)


class LensSessionTitleSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=160, allow_blank=False, trim_whitespace=True)


class LensRunCreateSerializer(serializers.Serializer):
    question = serializers.CharField(required=False, allow_blank=True)
    idempotency_key = serializers.CharField(required=False, allow_blank=True, max_length=128)


class LensOrgSettingsSerializer(serializers.Serializer):
    default_agent_model_ref = serializers.UUIDField(required=False, allow_null=True)


class LensChatBindingEnsureSerializer(serializers.Serializer):
    backup_config_id = serializers.IntegerField(min_value=1)
    backup_source_snapshot_id = serializers.IntegerField(min_value=1)
    backup_snapshot_directory_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    source_path = serializers.CharField(required=False, allow_blank=True, max_length=500)
    gateway_link_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)


class LensChatBindingSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    backup_config_id = serializers.IntegerField()
    backup_source_snapshot_id = serializers.IntegerField()
    backup_snapshot_directory_id = serializers.IntegerField(allow_null=True)
    source_path = serializers.CharField()
    gateway_link_id = serializers.IntegerField()
    gateway_name = serializers.CharField()
    gateway_scope = serializers.CharField()
    knowledge_source_id = serializers.IntegerField(allow_null=True)
    knowledge_source_status = serializers.CharField(allow_null=True)
    sl_assistant_uuid = serializers.CharField(allow_null=True)
    is_active = serializers.BooleanField()
    ready_for_chat = serializers.BooleanField(required=False)


class LensCopilotGatewayOptionSerializer(serializers.Serializer):
    gateway_link_id = serializers.IntegerField()
    gateway_id = serializers.IntegerField()
    name = serializers.CharField()
    scope = serializers.CharField()
    is_platform_default = serializers.BooleanField()
    sidecar_status = serializers.CharField()
    online = serializers.BooleanField()
    hfl_usable = serializers.BooleanField()
    copilot_eligible = serializers.BooleanField()
