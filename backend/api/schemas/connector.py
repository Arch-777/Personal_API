import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConnectorResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: uuid.UUID
	platform: str
	platform_email: str | None = None
	status: str
	last_synced: datetime | None = None
	error_message: str | None = None
	metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_json")
	created_at: datetime
	updated_at: datetime


class ConnectorSyncResponse(BaseModel):
	status: str
	platform: str


class ConnectorDisconnectResponse(BaseModel):
	"""Returned after a successful DELETE /connectors/{platform} call."""

	disconnected: list[str]
	"""All platform connector rows that were removed (may include Google siblings)."""
	items_deleted: int
	"""Number of synced item rows deleted. 0 when delete_data=false (the default)."""

