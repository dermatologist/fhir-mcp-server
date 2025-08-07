import logging

from fhir_mcp_server.oauth import (
    OAuthServerProvider,
    ServerConfigs,
)
from typing import Dict
from pydantic import AnyHttpUrl
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.fastmcp.server import FastMCP


logger: logging.Logger = logging.getLogger(__name__)

configs: ServerConfigs = ServerConfigs()

server_provider: OAuthServerProvider = OAuthServerProvider(configs=configs)

def configure_mcp_server(disable_auth: bool) -> FastMCP:
    """
    Configure and instantiate the FastMCP server instance.
    If disable_auth is True, the server will be started without authorization.
    Returns a FastMCP instance.
    """
    fastmcp_kwargs: Dict = {
        "name": "FHIR MCP Server",
        "instructions": "This server implements the HL7 FHIR MCP for secure, standards-based access to FHIR resources",
        "host": configs.mcp_host,
        "port": configs.mcp_port,
        "json_response": True,
        "stateless_http": True,
    }
    if not disable_auth:
        logger.debug("Enabling authorization for FHIR MCP server.")
        auth_settings: AuthSettings = AuthSettings(
            issuer_url=AnyHttpUrl(configs.effective_server_url),
            client_registration_options=ClientRegistrationOptions(
                enabled=True,
                valid_scopes=configs.scopes,
                default_scopes=configs.scopes,
            ),
        )
        fastmcp_kwargs["auth_server_provider"] = server_provider
        fastmcp_kwargs["auth"] = auth_settings
    else:
        logger.warning("MCP authentication is disabled.")
    return FastMCP(**fastmcp_kwargs)
