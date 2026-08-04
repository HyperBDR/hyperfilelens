from django.test import SimpleTestCase

from apps.lens_bridge.services import retrieval_policy


class ManagedChatRetrievalPolicyTests(SimpleTestCase):
    def test_enables_hidden_and_clears_builtin_excludes(self):
        policy = retrieval_policy.managed_chat_retrieval_policy()
        self.assertEqual(
            policy,
            {
                "include_hidden": True,
                "exclude_dirs": [],
                "exclude_extensions": [],
            },
        )
