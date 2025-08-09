from fastapi import FastAPI
from .core.config import settings
from .api.endpoints import auth
from .api.endpoints import users
from .api.endpoints import cars
from .api.endpoints import parts
from .api.endpoints import build_lists


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_STR}/openapi.json",
    debug=settings.DEBUG,
)

app.include_router(users.router, prefix=settings.API_STR + "/users", tags=["users"])
app.include_router(cars.router, prefix=settings.API_STR + "/cars", tags=["cars"])
app.include_router(
    build_lists.router, prefix=settings.API_STR + "/build-lists", tags=["build_lists"]
)
app.include_router(parts.router, prefix=settings.API_STR + "/parts", tags=["parts"])
app.include_router(auth.router, prefix=settings.API_STR + "/auth", tags=["auth"])


@app.get("/")
def read_root():
    return {"Hello": "World"}
