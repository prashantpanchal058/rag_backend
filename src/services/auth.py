import httpx
from fastapi import Request, HTTPException

CLERK_JWKS_URL = "https://api.clerk.dev/v1/jwks"

async def get_current_user(request: Request):
    token = request.headers.get("Authorization")

    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    token = token.replace("Bearer ", "")

    async with httpx.AsyncClient() as client:
        jwks = await client.get(CLERK_JWKS_URL)

    return {"user_id": "extracted_clerk_user_id"}