import click
import logging

from fhir_mcp_server.utils import (
    create_async_fhir_client,
    get_default_headers,
)
from fhir_mcp_server.oauth import (
    OAuthServerProvider,
    OAuthToken,
    ServerConfigs,
)
from fhirpy import AsyncFHIRClient
from typing import Dict
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken


logger: logging.Logger = logging.getLogger(__name__)

configs: ServerConfigs = ServerConfigs()

server_provider: OAuthServerProvider = OAuthServerProvider(configs=configs)


@click.pass_context
async def get_user_access_token(click_ctx: click.Context) -> OAuthToken | None:
    """
    Retrieve the access token for the authenticated user.
    Returns an OAuthToken if available, otherwise raises an error.
    """
    if configs.server_access_token:
        logger.debug("Using configured FHIR access token for user.")
        return OAuthToken(access_token=configs.server_access_token, token_type="Bearer")

    user_token: AccessToken | None = get_access_token()
    if not user_token:
        logger.error("Failed to obtain client access token.")
        raise ValueError("Failed to obtain client access token.")

    logger.debug("Obtained client access token from context.")

    # Return the FHIR access token
    return user_token  # type: ignore


@click.pass_context
async def get_async_fhir_client(click_ctx: click.Context) -> AsyncFHIRClient:
    """
    Get an async FHIR client with the user's access token.
    Returns an AsyncFHIRClient instance.
    """
    client_kwargs: Dict = {
        "config": configs,
        "extra_headers": get_default_headers(),
    }

    disable_auth: bool = click_ctx.obj.get("disable_auth") if click_ctx.obj else False
    if not disable_auth:
        user_token: AccessToken | None = await get_user_access_token()  # type: ignore
        if not user_token:
            logger.error("User is not authenticated.")
            raise ValueError("User is not authenticated.")
        client_kwargs["access_token"] = user_token.token
    else:
        logger.debug("FHIR authentication is disabled.")
    return await create_async_fhir_client(**client_kwargs)
