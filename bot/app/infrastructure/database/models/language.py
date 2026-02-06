from pydantic import BaseModel, Field


class LanguageModel(BaseModel):
    id: int = Field(..., description="Primary key of the language")
    code: str = Field(..., description="Unique language code (e.g. 'ru', 'en', 'dev')")
    is_default: bool = Field(
        ..., description="Flag indicating whether language is default for new users"
    )

    class Config:
        from_attributes = True
        frozen = True
        extra = "forbid"
