import logging

from fhir_mcp_server.oauth import (
    handle_failed_authentication,
    OAuthServerProvider,
    ServerConfigs,
)
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from mcp.server.fastmcp.server import FastMCP


logger: logging.Logger = logging.getLogger(__name__)

configs: ServerConfigs = ServerConfigs()

server_provider: OAuthServerProvider = OAuthServerProvider(configs=configs)


def register_mcp_routes(
    mcp: FastMCP,
    server_provider: OAuthServerProvider,
) -> None:
    """
    Register custom routes for the FastMCP server instance.
    """
    logger.debug("Registering custom MCP routes.")

    @mcp.custom_route("/oauth/callback", methods=["GET"])
    async def handle_auth_server_callback(request: Request) -> Response:
        """Handle MCP OAuth redirect."""
        code: str | None = request.query_params.get("code")
        state: str | None = request.query_params.get("state")

        if not code or not state:
            return handle_failed_authentication("Missing code or state parameter")

        try:
            redirect_uri: str = await server_provider.handle_mcp_oauth_callback(
                code, state
            )
            return RedirectResponse(status_code=302, url=redirect_uri)
        except Exception as ex:
            logger.error(
                "Error occurred while handling MCP oauth callback. Caused by, ",
                exc_info=ex,
            )
            return handle_failed_authentication("Something went wrong.")
