import logging
from typing import Any, Dict, List

from mcp.server.fastmcp.server import FastMCP
from pydantic import Field
from typing_extensions import Annotated

from fhir_mcp_server.oauth import OAuthServerProvider, ServerConfigs
from fhir_mcp_server.utils import (
    get_operation_outcome,
    get_operation_outcome_exception,
    get_operation_outcome_required_error,
)
from fhirpy import AsyncFHIRClient
from fhirpy.lib import AsyncFHIRResource
from fhirpy.base.exceptions import OperationOutcome
from fhirpy.base.searchset import Raw

from .context import get_async_fhir_client

logger: logging.Logger = logging.getLogger(__name__)

configs: ServerConfigs = ServerConfigs()

server_provider: OAuthServerProvider = OAuthServerProvider(configs=configs)


def register_search_tool(mcp: FastMCP) -> None:

    @mcp.tool(
        description=(
            "Executes a standard FHIR `search` interaction on a given resource type, returning a bundle or list of matching resources. "
            "Use this when you need to query for multiple resources based on one or more search-parameters. "
            "Do not use this tool for create, update, or delete operations, and be aware that large result sets may be paginated by the FHIR server."
        )
    )
    async def search(
        type: Annotated[
            str,
            Field(
                description="The FHIR resource type name. Must exactly match one of the resource types supported by the server",
                examples=["MedicationRequest", "Condition", "Procedure"],
            ),
        ],
        searchParam: Annotated[
            Dict[str, str | List[str]],
            Field(
                description=(
                    "A mapping of FHIR search parameter names to their values. "
                    "Only include parameters supported for the resource type, as listed by `get_capabilities`."
                ),
                examples=[
                    '{"family": "Smith"}',
                    '{"date": ["ge1970-01-01", "lt2000-01-01"]}',
                ],
            ),
        ],
    ) -> Annotated[
        list[Dict[str, Any]] | Dict[str, Any],
        Field(
            description="A dictionary containing the full FHIR resource instance matching the search criteria."
        ),
    ]:
        try:
            logger.debug(f"Invoked with type='{type}' and searchParam={searchParam}")
            if not type:
                logger.error(
                    "Unable to perform search operation: 'type' is a mandatory field."
                )
                return await get_operation_outcome_required_error("type")

            client: AsyncFHIRClient = await get_async_fhir_client()
            async_resources: list[AsyncFHIRResource] = (
                await client.resources(type).search(Raw(**searchParam)).fetch()
            )
            resources: list[Dict[str, Any]] = []
            for async_resource in async_resources:
                resources.append(async_resource.serialize())
            return resources
        except ValueError as ex:
            logger.exception(
                f"User does not have permission to perform FHIR '{type}' resource search operation. Caused by, ",
                exc_info=ex,
            )
            return await get_operation_outcome(
                code="forbidden",
                diagnostics=f"The user does not have the rights to perform search operation.",
            )
        except OperationOutcome as ex:
            logger.exception(
                f"FHIR server returned an OperationOutcome error while searching the resource: '{type}', Caused by,",
                exc_info=ex,
            )
            return ex.resource["issue"] or await get_operation_outcome_exception()
        except Exception as ex:
            logger.exception(
                f"An unexpected error occurred during the FHIR search operation for resource: '{type}'. Caused by, ",
                exc_info=ex,
            )
        return await get_operation_outcome_exception()
