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
from fhirpy.base.exceptions import OperationOutcome
from typing import Dict, Any, List
from typing_extensions import Annotated
from pydantic import Field
from mcp.server.fastmcp.server import FastMCP

from .context import get_async_fhir_client

logger: logging.Logger = logging.getLogger(__name__)

configs: ServerConfigs = ServerConfigs()

server_provider: OAuthServerProvider = OAuthServerProvider(configs=configs)

def register_delete_tool(mcp: FastMCP) -> None:

    @mcp.tool(
        description=(
            "Execute a FHIR `delete` interaction on a specific resource instance. "
            "Use this tool when you need to remove a single resource identified by its logical ID or optionally filtered by search parameters. "
            "The optional `id` parameter must match an existing resource instance when present. "
            "If you include `searchParam`, the server will perform a conditional delete, deleting the resource only if it matches the given criteria. "
            "If you supply `operation`, it will execute the named FHIR operation (e.g., `$expunge`) on the resource. "
            "This tool returns a FHIR `OperationOutcome` describing success or failure of the deletion."
        )
    )
    async def delete(
        type: Annotated[
            str,
            Field(
                description="The FHIR resource type name. Must exactly match one of the resource types supported by the server.",
                examples=["ServiceRequest", "Appointment", "HealthcareService"],
            ),
        ],
        id: Annotated[
            str,
            Field(description="The logical ID of a specific FHIR resource instance."),
        ] = "",
        searchParam: Annotated[
            Dict[str, str | List[str]],
            Field(
                description=(
                    "A mapping of FHIR search parameter names to their desired values. "
                    "These parameters refine queries for operation-specific query qualifiers. "
                    "Only parameters exposed by `get_capabilities` for that resource type are valid. "
                ),
                examples=['{"category": "laboratory", "status": ["active"]}'],
            ),
        ] = {},
        operation: Annotated[
            str,
            Field(
                description=(
                    "The name of a custom FHIR operation or extended query defined for the resource"
                    "Must match one of the operation names returned by `get_capabilities`."
                ),
                examples=["$expand"],
            ),
        ] = "",
    ) -> Annotated[
        Dict[str, Any],
        Field(
            description="A dictionary containing the confirmation of deletion or details on why deletion failed."
        ),
    ]:
        try:
            logger.debug(
                f"Invoked with type='{type}', id={id}, searchParam={searchParam}, and operation={operation}"
            )
            if not type:
                logger.error(
                    "Unable to perform delete operation: 'type' is a mandatory field."
                )
                return await get_operation_outcome_required_error("type")
            if not id and not searchParam:
                logger.error(
                    "Unable to perform delete operation: 'id' or 'searchParam' is required."
                )
                return await get_operation_outcome_required_error("id")

            client: AsyncFHIRClient = await get_async_fhir_client()
            bundle = await client.resource(resource_type=type, id=id).execute(
                operation=operation or "", method="DELETE", params=searchParam
            )
            if isinstance(bundle, Dict):
                return await get_bundle_entries(bundle=bundle)
            return await get_operation_outcome(
                severity="information",
                code="SUCCESSFUL_DELETE",
                diagnostics="Successfully deleted resource(s).",
            )
        except ValueError as ex:
            logger.exception(
                f"User does not have permission to perform FHIR '{type}' resource delete operation. Caused by, ",
                exc_info=ex,
            )
            return await get_operation_outcome(
                code="forbidden",
                diagnostics=f"The user does not have the rights to perform delete operation.",
            )
        except OperationOutcome as ex:
            logger.exception(
                f"FHIR server returned an OperationOutcome error while deleting the resource: '{type}', Caused by,",
                exc_info=ex,
            )
            return ex.resource["issue"] or await get_operation_outcome_exception()
        except Exception as ex:
            logger.exception(
                f"An unexpected error occurred during the FHIR delete operation for resource: '{type}'. Caused by, ",
                exc_info=ex,
            )
        return await get_operation_outcome_exception()
