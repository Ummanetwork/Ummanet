from pydantic import BaseModel, Field


class TranslationKeyModel(BaseModel):
    id: int = Field(..., description="Primary key of translation key")
    identifier: str = Field(
        ..., description="Unique identifier used in code to reference the translation"
    )
    description: str | None = Field(
        None, description="Optional human-readable description of the key"
    )

    class Config:
        from_attributes = True
        frozen = True
        extra = "forbid"
