"""FastAPI application entrypoint."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.stocks import router as stocks_router
from app.config import get_finmind_token
from app.data.exceptions import FinMindError

app = FastAPI(title="Taiwan Stock Analyzer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(FinMindError)
async def finmind_error_handler(request: Request, exc: FinMindError):
    """Handle all FinMind and data layer exceptions with unified format."""
    status_code = getattr(exc, "status_code", 400)
    return JSONResponse(
        status_code=status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "hint": exc.hint,
        },
    )


app.include_router(stocks_router)


@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "finmind_token_configured": bool(get_finmind_token()),
    }
