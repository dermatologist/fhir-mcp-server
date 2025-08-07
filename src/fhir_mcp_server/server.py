# Copyright (c) 2025, WSO2 LLC. (https://www.wso2.com/) All Rights Reserved.

# WSO2 LLC. licenses this file to you under the Apache License,
# Version 2.0 (the "License"); you may not use this file except
# in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied. See the License for the
# specific language governing permissions and limitations
# under the License.

import click
import logging

from fhir_mcp_server.utils import (
    create_async_fhir_client,
    get_bundle_entries,
    get_default_headers,
    get_operation_outcome,
    get_operation_outcome_exception,
    get_operation_outcome_required_error,
    get_capability_statement,
    trim_resource_capabilities,
)
from fhir_mcp_server.oauth import (
    handle_failed_authentication,
    OAuthServerProvider,
    OAuthToken,
    ServerConfigs,
)
from fhirpy import AsyncFHIRClient
from fhirpy.lib import AsyncFHIRResource
from fhirpy.base.exceptions import OperationOutcome, ResourceNotFound
from fhirpy.base.searchset import Raw
from typing import Dict, Any, List
from typing_extensions import Annotated
from pydantic import AnyHttpUrl, Field
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.fastmcp.server import FastMCP

from .tools.context import get_user_access_token, get_async_fhir_client
from .tools.capabilities import register_capabilities_tool
from .tools.search import register_search_tool
from .tools.read import register_read_tool
from .tools.create import register_create_tool
from .tools.update import register_update_tool
from .tools.delete import register_delete_tool

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


def register_mcp_tools(mcp: FastMCP) -> None:
    """
    Register tool functions for the FastMCP server instance.
    """
    logger.debug("Registering MCP tools.")

    register_capabilities_tool(mcp)
    register_search_tool(mcp)
    register_read_tool(mcp)
    register_create_tool(mcp)
    register_update_tool(mcp)
    register_delete_tool(mcp)

@click.command()
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse", "streamable-http"]),
    default="streamable-http",
    show_default=True,
    help="Transport protocol to use",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARN", "ERROR"], case_sensitive=False),
    default="INFO",
    show_default=True,
    help="Log level to use",
)
@click.option(
    "--disable-auth",
    is_flag=True,
    default=False,
    show_default=True,
    help="Disable authorization between MCP client and MCP server. [default: False]",
)
@click.pass_context
def main(
    click_ctx: click.Context, transport, log_level, disable_auth
) -> int:
    """
    FHIR MCP Server - helping you expose any FHIR Server or API as a MCP Server.
    """
    # Store CLI options in context for downstream access
    click_ctx.ensure_object(dict)
    click_ctx.obj["disable_auth"] = disable_auth

    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="[%(asctime)s] %(levelname)s {%(name)s.%(funcName)s:%(lineno)d} - %(message)s",
    )
    try:
        mcp: FastMCP = configure_mcp_server(disable_auth)
        register_mcp_tools(mcp=mcp)
        register_mcp_routes(
            mcp=mcp, server_provider=server_provider
        )
        logger.info(f"Starting FHIR MCP server with {transport} transport")
        mcp.run(transport=transport)
    except Exception as ex:
        logger.error(
            f"Unable to run the FHIR MCP server. Caused by, %s", ex, exc_info=True
        )
        return 1
    return 0
