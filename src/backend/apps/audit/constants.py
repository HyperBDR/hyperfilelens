"""Audit domain constants."""


class AuditAction:
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ACCESS = "access"
    EXECUTE = "execute"
    LOGIN = "login"
    LOGOUT = "logout"
    EXPORT = "export"
    IMPORT = "import"
    ENABLE = "enable"
    DISABLE = "disable"

    TASK_CREATE = "task.create"
    TASK_FINISH = "task.finish"
    ALERT_ACK = "alert.ack"
    ALERT_RESOLVE = "alert.resolve"
    ALERT_POLICY_CREATE = "alert.policy.create"
    ALERT_POLICY_UPDATE = "alert.policy.update"
    ALERT_POLICY_DELETE = "alert.policy.delete"
    RESTORE_RUN = "restore.restore_plan.run"
    NODE_TASK_DISPATCH = "node_task.dispatch"
    NOTIFICATION_DELIVERY = "notification.delivery_attempt"


class AuditResourceType:
    USER = "user"
    TASK = "task"
    ALERT = "alert"
    ALERT_POLICY = "alert_policy"
    RESTORE_PLAN = "restore_plan"
    NODE_TASK = "node_task"
    NOTIFICATION = "notification_delivery"
    NOTIFICATION_CHANNEL = "notification_channel"
    NODE = "node"
    REPOSITORY = "repository"
    POLICY = "policy"
    ORGANIZATION = "organization"
    SYSTEM = "system"
    SESSION = "session"


class AuditTargetType:
    TASK = "task"
    ALERT = "alert"
    RESTORE_PLAN = "restore_plan"
    NODE_TASK = "node_task"
    NOTIFICATION_DELIVERY = "notification_delivery"


class AuditResult:
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
