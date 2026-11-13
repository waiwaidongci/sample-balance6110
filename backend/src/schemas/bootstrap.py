from pydantic import BaseModel,Field
class BootstrapInput(BaseModel):
    replicates:int=Field(default=200,ge=20,le=1000)
    seed:int=Field(default=20261113,ge=0,le=2147483647)
