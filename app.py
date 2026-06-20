"""TrustMatch enclave server (runs INSIDE the TDX confidential VM).

Endpoints
  GET  /attestation        -> quote + enclave public key (client verifies, then encrypts)
  POST /submit             -> {sealed profile} ; decrypt in-enclave, embed, store
  GET  /result/{token}     -> poll your match (connection code) ; reveals only a handle
  GET  /stats              -> content-free aggregate counts (stage safety net)
  POST /admin/match-round  -> presenter triggers the one synchronized batch round
  GET  /                   -> mobile web client

The enclave PRIVATE key is generated at startup and never leaves this process.
Raw profile text is decrypted, embedded, and dropped -- only the vector is kept.
"""
from __future__ import annotations

import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import attestation
from .crypto import EnclaveKeys
from .matching import embed
from .store import Store

HERE = os.path.dirname(__file__)
WEB_DIR = os.path.join(os.path.dirname(HERE), "web")
ADMIN_TOKEN = os.environ.get("TRUSTMATCH_ADMIN_TOKEN", "let-me-match")
MATCH_THRESHOLD = float(os.environ.get("TRUSTMATCH_THRESHOLD", "0.15"))

app = FastAPI(title="TrustMatch enclave")

KEYS = EnclaveKeys.generate()      # private key lives only in enclave RAM
STORE = Store()


class SealedPayload(BaseModel):
    epk: str
    nonce: str
    ct: str


@app.get("/attestation")
def attestation_endpoint():
    quote = attestation.get_quote(KEYS.public_key_b64)
    return {
        "public_key": KEYS.public_key_b64,
        "quote": attestation.quote_to_dict(quote),
    }


@app.post("/submit")
def submit(payload: SealedPayload):
    try:
        plaintext = KEYS.decrypt(payload.model_dump())
    except Exception:
        raise HTTPException(400, "decryption failed (not sealed to this enclave?)")
    try:
        profile = json.loads(plaintext)
        answers = profile.get("answers", {})
        # Concatenate all rich answers into one document to embed.
        text = "\n".join(str(v) for v in answers.values())
        handle = str(profile.get("handle") or "someone in the room")
    except Exception:
        raise HTTPException(400, "malformed profile")

    if not text.strip():
        raise HTTPException(400, "empty profile")

    vector = embed(text)
    ids = STORE.add(vector, display_handle=handle)
    # We return a token; raw text has already been discarded.
    return {"ok": True, "token": ids["token"]}


@app.get("/result/{token}")
def result(token: str):
    res = STORE.result_for(token)
    if res is None:
        raise HTTPException(404, "unknown token")
    return {
        "round_done": STORE.stats()["round_done"],
        "matched": res.matched,
        "peer_handle": res.peer_handle,
        "connection_code": res.connection_code,
        "score": res.score,
    }


@app.get("/stats")
def stats():
    return STORE.stats()


@app.post("/admin/match-round")
def match_round(admin_token: str = ""):
    if admin_token != ADMIN_TOKEN:
        raise HTTPException(403, "bad admin token")
    return STORE.run_match_round(threshold=MATCH_THRESHOLD)


@app.get("/")
def index():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


if os.path.isdir(WEB_DIR):
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
