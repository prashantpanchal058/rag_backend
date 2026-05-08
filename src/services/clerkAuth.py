from fastapi import Request, HTTPException
from clerk_backend_api import Clerk
from clerk_backend_api.security.types import AuthenticateRequestOptions
import os

CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY")

clerk_sdk = Clerk(CLERK_SECRET_KEY)  # move outside

def get_current_user_clerk_id(request: Request):
    try:
        request_state = clerk_sdk.authenticate_request(
            request,
            options=AuthenticateRequestOptions(
                authorized_parties=["http://localhost:3000"]
            ),
        )

        if not request_state.is_signed_in:
            raise HTTPException(status_code=401, detail="User not signed in")

        clerk_id = request_state.payload.get("sub")

        if not clerk_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")

        return clerk_id

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
