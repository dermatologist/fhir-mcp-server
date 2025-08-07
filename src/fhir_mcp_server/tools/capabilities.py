import logging

from fhir_mcp_server.utils import (
    get_operation_outcome,
    get_operation_outcome_exception,
    get_capability_statement,
    trim_resource_capabilities,
)
from fhir_mcp_server.oauth import (
    OAuthServerProvider,
    ServerConfigs,
)
from typing import Dict, Any
from typing_extensions import Annotated
from pydantic import Field
from mcp.server.fastmcp.server import FastMCP

logger: logging.Logger = logging.getLogger(__name__)

configs: ServerConfigs = ServerConfigs()

server_provider: OAuthServerProvider = OAuthServerProvider(configs=configs)

def register_capabilities_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        description=(
            "Retrieves metadata about a specified FHIR resource type, including its supported search parameters and custom operations. "
            "This tool MUST always be invoked before performing any resource operation (such as search, read, create, update, or delete) "
            "to discover the valid searchParams and operations permitted for that resource type. "
            "Do not use this tool to fetch actual resources."
        )
    )
    async def get_capabilities(
        type: Annotated[
            str,
            Field(
                description=(
                    "The FHIR resource type name. Must exactly match one of the core or "
                    "profile-defined resource types as per the FHIR specification."
                ),
                examples=["Patient", "Observation", "Encounter"],
            ),
        ],
    ) -> Annotated[
        Dict[str, Any],
        Field(
            description=(
                "A dictionary containing: "
                "'type': The requested resource type (if supported by the system) or empty. "
                "'searchParam': A mapping of FHIR search parameter names to their descriptions. Each key is a parameter name "
                "(e.g., family, _id, _lastUpdated), and each value is a string describing the parameter's meaning and usage constraints. "
                "'operation': A mapping of custom FHIR operation names to their descriptions. Each key is an operation name "
                "(e.g., $validate), and each value is a string explaining the operation's purpose and usage. "
                "'interaction': A list of supported interactions for the resource type (e.g., read, search-type, create). "
                "'searchInclude': A list of supported _include parameters for the resource type, indicating which related resources can be included. "
                "'searchRevInclude': A list of supported _revinclude parameters for the resource type, indicating which reverse-included resources can be included."
            )
        ),
    ]:
        try:
            logger.debug(f"Invoked with resource_type='{type}'")
            data: Dict[str, Any] = await get_capability_statement(
                configs.metadata_url
            )
            for resource in data["rest"][0]["resource"]:
                if resource.get("type") == type:
                    logger.info(
                        f"Resource type '{type}' found in the CapabilityStatement."
                    )
                    return {
                        "type": resource.get("type"),
                        "searchParam": trim_resource_capabilities(
                            resource.get("searchParam", [])
                        ),
                        "operation": trim_resource_capabilities(
                            resource.get("operation", [])
                        ),
                        "interaction": resource.get("interaction", []),
                        "searchInclude": resource.get("searchInclude", []),
                        "searchRevInclude": resource.get("searchRevInclude", []),
                    }
            logger.info(f"Resource type '{type}' not found in the CapabilityStatement.")
            return await get_operation_outcome(
                code="not-supported",
                diagnostics=f"The interaction, operation, resource or profile {type} is not supported.",
            )
        except Exception as ex:
            logger.exception(
                f"Error while executing the FHIR metadata interaction for resource_type '{type}'. Caused by, ",
                exc_info=ex,
            )
        return await get_operation_outcome_exception()
