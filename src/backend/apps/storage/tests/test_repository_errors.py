from django.test import SimpleTestCase

from apps.storage.services.internal.repository_errors import (
    REPOSITORY_ALREADY_EXISTS_CODE,
    agent_repository_failure_message,
    agent_result_has_repository_conflict,
)


class RepositoryAgentErrorTests(SimpleTestCase):
    def test_detects_structured_repository_conflict(self):
        self.assertTrue(
            agent_result_has_repository_conflict(
                {"error_code": REPOSITORY_ALREADY_EXISTS_CODE}
            )
        )

    def test_detects_kopia_existing_data_message_from_nested_create_result(self):
        self.assertTrue(
            agent_result_has_repository_conflict(
                {
                    "repository_create": {
                        "stderr": (
                            "unable to get repository storage: "
                            "found existing data in storage location"
                        )
                    }
                }
            )
        )

    def test_does_not_treat_status_output_as_an_initialize_conflict(self):
        self.assertFalse(
            agent_result_has_repository_conflict(
                {
                    "repository_status": {
                        "stderr": "found existing data in storage location"
                    }
                }
            )
        )

    def test_prefers_nested_command_reason_over_generic_exit(self):
        result = {"repository_create": {"stderr": "permission denied"}}

        self.assertEqual(
            agent_repository_failure_message(
                result,
                last_error="exit 1: exit status 1",
            ),
            "permission denied",
        )

    def test_keeps_specific_agent_error(self):
        result = {"repository_create": {"stderr": "permission denied"}}

        self.assertEqual(
            agent_repository_failure_message(
                result,
                last_error="repository task timed out",
            ),
            "repository task timed out",
        )
