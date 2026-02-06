from pydantic import BaseModel, Field


class TranslationModel(BaseModel):
    id: int = Field(..., description="Primary key of translation record")
    language_id: int = Field(..., description="Foreign key referencing language")
    key_id: int = Field(..., description="Foreign key referencing translation key")
    value: str | None = Field(
        None, description="Translated text value (None for DEV language)"
    )

    class Config:
        from_attributes = True
        frozen = True
        extra = "forbid"
