from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.lens_bridge.models import LensGatewayLink
from apps.lens_bridge.services import gateway_readiness


def _link(*, origin=LensGatewayLink.Origin.USER, sidecar_status=LensGatewayLink.SidecarStatus.ONLINE):
    return SimpleNamespace(
        gateway_id=21,
        gateway=SimpleNamespace(role="gateway"),
        sl_lensnode_uuid="c5381ee5-4569-4ffb-8915-6f72705fa6c7",
        origin=origin,
        sidecar_status=sidecar_status,
    )


class GatewayReadinessTests(SimpleTestCase):
    @patch("apps.lens_bridge.services.gateway_readiness.agent_ws_routable", return_value=True)
    def test_hfl_gateway_bundle_is_copilot_eligible_when_fully_ready(self, mock_routable):
        state = gateway_readiness.gateway_runtime_state(_link(), sl_runtime_status="online")

        self.assertTrue(state["hfl_managed"])
        self.assertTrue(state["hfl_agent_online"])
        self.assertTrue(state["hfl_sidecar_online"])
        self.assertTrue(state["hfl_usable"])
        self.assertTrue(state["copilot_eligible"])
        mock_routable.assert_called_once_with(agent_id=21)

    def test_unmapped_sl_lensnode_is_discoverable_but_not_hfl_usable(self):
        state = gateway_readiness.gateway_runtime_state(None, sl_runtime_status="online")

        self.assertFalse(state["hfl_managed"])
        self.assertFalse(state["hfl_agent_online"])
        self.assertFalse(state["hfl_sidecar_online"])
        self.assertFalse(state["hfl_usable"])
        self.assertFalse(state["copilot_eligible"])

    @patch("apps.lens_bridge.services.gateway_readiness.agent_ws_routable", return_value=False)
    def test_hfl_gateway_without_routable_agent_is_not_usable(self, _mock_routable):
        state = gateway_readiness.gateway_runtime_state(_link())

        self.assertFalse(state["hfl_usable"])
        self.assertFalse(state["copilot_eligible"])
