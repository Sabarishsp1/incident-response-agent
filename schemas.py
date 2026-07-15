from pydantic import BaseModel, Field


class RelatedIncident(BaseModel):
    """Represents a previously resolved incident related to the current alert."""
    incident_id: str = Field(..., description="Unique identifier of the related incident")
    description: str = Field(..., description="Short description of the incident")
    resolution: str = Field(..., description="How the incident was resolved")


class Runbook(BaseModel):
    runbook_id: str = Field(..., description="Unique runbook identifier")
    title: str = Field(..., description="Runbook title")
    category: str = Field(..., description="Incident category")
    summary: str = Field(..., description="Brief description of the runbook")
    remediation_steps: list[str] = Field(
        ..., min_length=1, description="Ordered remediation steps"
    )
    related_incidents: list[RelatedIncident] = Field(
        default_factory=list,
        description="Similar incidents that can assist with troubleshooting"
    )


class SearchResult(BaseModel):
    runbook: Runbook
    relevance_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence that this runbook matches the search query"
    )


class SearchRunbooksResponse(BaseModel):
    results: list[SearchResult] = Field(default_factory=list)