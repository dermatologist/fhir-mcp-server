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

def register_update_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        description=(
            "Performs a FHIR `update` interaction by replacing an existing resource instance's content with the provided payload. "
            "Use it when you need to overwrite a resource's data in its entirety, such as correcting or completing a record, "
            "and you already know the resource's logical id. "
            "Optionally, you can include searchParam for conditional updates (e.g., only update if the resource matches certain criteria) "
            "or specify a custom operation (e.g., `$validate` to run validation before updating) "
            "The tool returns the updated resource or an OperationOutcome detailing any errors."
        )
    )
    async def update(
        type: Annotated[
            str,
            Field(
                description="The FHIR resource type name. Must exactly match one of the resource types supported by the server.",
                examples=["Location", "Organization", "Coverage"],
            ),
        ],
        id: Annotated[
            str,
            Field(description="The logical ID of a specific FHIR resource instance."),
        ],
        payload: Annotated[
            Dict[str, Any],
            Field(
                description=(
                    "The complete JSON representation of the FHIR resource, containing all required elements and any optional data. "
                    "Servers replace the existing resource with this exact content, so the payload must include all mandatory fields "
                    "defined by the resource's profile and any previous data you wish to preserve."
                )
            ),
        ],
        searchParam: Annotated[
            Dict[str, str | List[str]],
            Field(
                description=(
                    "A mapping of FHIR search parameter names to their desired values. "
                    "These parameters refine queries for operation-specific query qualifiers. "
                    "Only parameters exposed by `get_capabilities` for that resource type are valid. "
                ),
                examples=['{"patient":"Patient/54321","relationship":["father"]}'],
            ),
        ] = {},
        operation: Annotated[
            str,
            Field(
                description=(
                    "The name of a custom FHIR operation or extended query defined for the resource"
                    "Must match one of the operation names returned by `get_capabilities`."
                ),
                examples=["$lastn"],
            ),
        ] = "",
    ) -> Annotated[
        Dict[str, Any],
        Field(description="A dictionary containing the updated FHIR resource"),
    ]:
        try:
            logger.debug(
                f"Invoked with type='{type}', id={id}, payload={payload}, searchParam={searchParam}, and operation={operation}"
            )
            if not type:
                logger.error(
                    "Unable to perform update operation: 'type' is a mandatory field."
                )
                return await get_operation_outcome_required_error("type")

            client: AsyncFHIRClient = await get_async_fhir_client()
            bundle: dict = await client.resource(resource_type=type, id=id).execute(
                operation=operation or "",
                method="PUT",
                data={**payload, "id": id},
                params=searchParam,
            )
            return await get_bundle_entries(bundle=bundle)
        except ValueError as ex:
            logger.exception(
                f"User does not have permission to perform FHIR '{type}' resource update operation. Caused by, ",
                exc_info=ex,
            )
            return await get_operation_outcome(
                code="forbidden",
                diagnostics=f"The user does not have the rights to perform update operation.",
            )
        except OperationOutcome as ex:
            logger.exception(
                f"FHIR server returned an OperationOutcome error while updating the resource: '{type}', Caused by,",
                exc_info=ex,
            )
            return ex.resource["issue"] or await get_operation_outcome_exception()
        except Exception as ex:
            logger.exception(
                f"An unexpected error occurred during the FHIR update operation for resource: '{type}'. Caused by, ",
                exc_info=ex,
            )
        return await get_operation_outcome_exception()
