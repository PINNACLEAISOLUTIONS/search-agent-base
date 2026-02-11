from pydantic import BaseModel, Field, validator
from datetime import datetime


class Lead(BaseModel):
    """
    Represents a single Craigslist lead.
    Validates data types and ensuring critical fields exist.
    """

    id: str = Field(..., description="Unique Craigslist Post ID")
    title: str = Field(..., min_length=1, description="Listing Title")
    link: str = Field(
        ..., description="Full URL to the listing"
    )  # Can use HttpUrl but CL links sometimes weird
    region: str = Field(..., description="Craigslist Region Name")
    keyword: str = Field(..., description="Search Keyword matched")
    score: float = Field(0.0, ge=0.0, le=10.0, description="AI Relevance Score")
    classification: str = Field("UNKNOWN", description="Item Classification matches")
    price: str = Field("", description="Price string (e.g. '$150')")
    image: str = Field("", description="Image URL")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    posted_date: str = Field("", description="Original date posted on Craigslist")
    is_new: bool = Field(True)

    @validator("link")
    def validate_link(cls, v):
        if not v.startswith("http"):
            raise ValueError("Link must start with http")
        return v
