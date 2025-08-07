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

from fhir_mcp_server.oauth import (
    OAuthServerProvider,
    ServerConfigs,
)
from mcp.server.fastmcp.server import FastMCP

from .config import configure_mcp_server
from .routes import register_mcp_routes
from .tools.capabilities import register_capabilities_tool
from .tools.search import register_search_tool
from .tools.read import register_read_tool
from .tools.create import register_create_tool
from .tools.update import register_update_tool
from .tools.delete import register_delete_tool

logger: logging.Logger = logging.getLogger(__name__)

configs: ServerConfigs = ServerConfigs()

server_provider: OAuthServerProvider = OAuthServerProvider(configs=configs)

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
