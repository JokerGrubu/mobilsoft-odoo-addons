"""
Q-Commerce Webhook Controllers
"""

import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class QCommerceWebhookController(http.Controller):
    """Webhook receivers for Q-Commerce platform events"""

    @http.route(
        "/api/webhook/qcommerce/<string:platform>",
        type="jsonrpc",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def qcommerce_webhook(self, platform, **kw):
        """Receive webhook from Q-Commerce platform (Getir, Yemeksepeti, Vigo)"""
        try:
            _logger.info(f"Webhook received for platform: {platform}")

            Channel = request.env["qcommerce.channel"].sudo()
            channel = Channel.search(
                [("platform_type", "=", platform), ("active", "=", True)], limit=1
            )

            if not channel:
                return {"status": "error", "message": "Channel not found"}

            connector = channel._get_connector()
            result = connector._process_webhook(kw)

            return {
                "status": "success",
                "message": f"Webhook processed for {platform}",
                "result": result,
            }
        except Exception as e:
            _logger.error(f"Webhook error: {str(e)}")
            return {"status": "error", "message": str(e)}
