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


def register_create_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        description=(
            "Executes a FHIR `create` interaction to persist a new resource of the specified type. "
            "It is required to supply the full resource payload in JSON form. "
            "Use this tool when you need to add new data (e.g., a new Patient or Observation). "
            "Note that servers may reject resources that violate profiles or mandatory bindings."
        )
    )
    async def create(
        type: Annotated[
            str,
            Field(
                description="The FHIR resource type name. Must exactly match one of the resource types supported by the server.",
                examples=["Device", "CarePlan", "Goal"],
            ),
        ],
        payload: Annotated[
            Dict[str, Any],
            Field(
                description=(
                    "A JSON object representing the full FHIR resource body to be created. "
                    "It must include all required elements of the resource's profile."
                )
            ),
        ],
        searchParam: Annotated[
            Dict[str, str | List[str]],
            Field(
                description=(
                    "A mapping of FHIR search parameter names to their desired values. "
                    "These parameters refine queries for operation-specific query qualifiers. "
                    "Only parameters exposed by `get_capabilities` for that resource type are valid."
                ),
                examples=['{"address-city": "Boston", "address-state": ["NY"]}'],
            ),
        ] = {},
        operation: Annotated[
            str,
            Field(
                description=(
                    "The name of a custom FHIR operation or extended query defined for the resource"
                    "Must match one of the operation names returned by `get_capabilities`."
                ),
                examples=["$evaluate"],
            ),
        ] = "",
    ) -> Annotated[
        Dict[str, Any],
        Field(
            description=(
                "A dictionary containing the newly created FHIR resource, including server-assigned fields "
                "(id, meta.versionId, meta.lastUpdated, and any server-added extensions). Reflects exactly what was persisted."
            )
        ),
    ]:
        try:
            logger.debug(
                f"Invoked with type='{type}', payload={payload}, searchParam={searchParam}, and operation={operation}"
            )
            if not type:
                logger.error(
                    "Unable to perform create operation: 'type' is a mandatory field."
                )
                return await get_operation_outcome_required_error("type")

            client: AsyncFHIRClient = await get_async_fhir_client()
            bundle: dict = await client.resource(resource_type=type).execute(
                operation=operation or "", data=payload, params=searchParam
            )

            return await get_bundle_entries(bundle=bundle)
        except ValueError as ex:
            logger.exception(
                f"User does not have permission to perform FHIR '{type}' resource create operation. Caused by, ",
                exc_info=ex,
            )
            return await get_operation_outcome(
                code="forbidden",
                diagnostics=f"The user does not have the rights to perform create operation.",
            )
        except OperationOutcome as ex:
            logger.exception(
                f"FHIR server returned an OperationOutcome error while creating the resource: '{type}', Caused by,",
                exc_info=ex,
            )
            return ex.resource["issue"] or await get_operation_outcome_exception()
        except Exception as ex:
            logger.exception(
                f"An unexpected error occurred during the FHIR create operation for resource: '{type}'. Caused by, ",
                exc_info=ex,
            )
        return await get_operation_outcome_exception()
