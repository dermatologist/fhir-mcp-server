import logging

from fhir_mcp_server.utils import (
    get_bundle_entries,
    get_operation_outcome,
    get_operation_outcome_exception,
    get_operation_outcome_required_error,
)
from fhir_mcp_server.oauth import (
    OAuthServerProvider,
    ServerConfigs,
)
from fhirpy import AsyncFHIRClient
from fhirpy.base.exceptions import OperationOutcome, ResourceNotFound
from typing import Dict, Any, List
from typing_extensions import Annotated
from pydantic import Field
from mcp.server.fastmcp.server import FastMCP

from .context import get_async_fhir_client

logger: logging.Logger = logging.getLogger(__name__)

configs: ServerConfigs = ServerConfigs()

server_provider: OAuthServerProvider = OAuthServerProvider(configs=configs)

def register_read_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        description=(
            "Performs a FHIR `read` interaction to retrieve a single resource instance by its type and resource ID, "
            "optionally refining the response with search parameters or custom operations. "
            "Use it when you know the exact resource ID and require that one resource; do not use it for bulk queries. "
            "If additional query-level parameters or operations are needed (e.g., _elements or $validate), include them in searchParam or operation."
        )
    )
    async def read(
        type: Annotated[
            str,
            Field(
                description="The FHIR resource type name. Must exactly match one of the resource types supported by the server.",
                examples=["DiagnosticReport", "AllergyIntolerance", "Immunization"],
            ),
        ],
        id: Annotated[
            str,
            Field(description="The logical ID of a specific FHIR resource instance."),
        ],
        searchParam: Annotated[
            Dict[str, str | List[str]],
            Field(
                description=(
                    "A mapping of FHIR search parameter names to their desired values. "
                    "These parameters refine queries for operation-specific query qualifiers. "
                    "Only parameters exposed by `get_capabilities` for that resource type are valid."
                ),
                examples=['{"device-name": "glucometer", "identifier": ["12345"]}'],
            ),
        ] = {},
        operation: Annotated[
            str,
            Field(
                description=(
                    "The name of a custom FHIR operation or extended query defined for the resource "
                    "must match one of the operation names returned by `get_capabilities`."
                ),
                examples=["$everything"],
            ),
        ] = "",
    ) -> Annotated[
        Dict[str, Any],
        Field(
            description="A dictionary containing the single FHIR resource instance of the requested type and id."
        ),
    ]:
        try:
            logger.debug(
                f"Invoked with type='{type}', id={id}, searchParam={searchParam}, and operation={operation}"
            )
            if not type:
                logger.error(
                    "Unable to perform read operation: 'type' is a mandatory field."
                )
                return await get_operation_outcome_required_error("type")

            client: AsyncFHIRClient = await get_async_fhir_client()
            bundle: dict = await client.resource(resource_type=type, id=id).execute(
                operation=operation or "", method="GET", params=searchParam
            )

            return await get_bundle_entries(bundle=bundle)
        except ResourceNotFound as ex:
            logger.error(
                f"Resource of type '{type}' with id '{id}' not found. Caused by, ",
                exc_info=ex,
            )
            return await get_operation_outcome(
                code="not-found",
                diagnostics=f"The resource of type '{type}' with id '{id}' was not found.",
            )
        except ValueError as ex:
            logger.exception(
                f"User does not have permission to perform FHIR '{type}' resource read operation. Caused by, ",
                exc_info=ex,
            )
            return await get_operation_outcome(
                code="forbidden",
                diagnostics=f"The user does not have the rights to perform read operation.",
            )
        except OperationOutcome as ex:
            logger.exception(
                f"FHIR server returned an OperationOutcome error while reading the resource: '{type}', Caused by,",
                exc_info=ex,
            )
            return ex.resource["issue"] or await get_operation_outcome_exception()
        except Exception as ex:
            logger.exception(
                f"An unexpected error occurred during the FHIR read operation for resource: '{type}'. Caused by, ",
                exc_info=ex,
            )
        return await get_operation_outcome_exception()
