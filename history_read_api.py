"""Read-only integration API for the Caçador's live, tenant-scoped job history.

This module deliberately has no mutation of the job history and does not
accept the browser session as API authentication.
"""
from datetime import datetime, timezone
import secrets

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from itsdangerous import BadSignature, SignatureExpired


TOKEN_SALT = "job-hunter-history-read-v1"
TOKEN_MAX_AGE = 30 * 24 * 60 * 60


def register_history_read_api(app, require_auth, serializer, database, auth_record, mu):
    def bearer_error():
        raise HTTPException(
            status_code=401,
            detail="Token de integração ausente, inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    def account_version(user_id):
        if mu.enabled:
            user = mu.get_user(database, user_id)
            if not user:
                bearer_error()
            return int(user[4]), user
        record = auth_record()
        return int(record[2] if record else 0), None

    @app.post("/api/integrations/history-token")
    def issue_history_token(request: Request):
        """Mint a scoped token only for the currently logged-in browser user."""
        uid = require_auth(request)
        if not serializer or not database:
            raise HTTPException(503, "Integração indisponível")
        identity = str(uid) if mu.enabled else "owner"
        version, _ = account_version(uid)
        ticket = serializer.dumps(
            {"scope": "history:read", "identity": identity, "version": version},
            salt=TOKEN_SALT,
        )
        return JSONResponse(
            {"token": ticket, "token_type": "Bearer",
             "expires_in_seconds": TOKEN_MAX_AGE,
             "scope": "history:read"},
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )

    def require_history_bearer(request: Request):
        if not serializer or not database:
            raise HTTPException(503, "Integração indisponível")
        authorization = request.headers.get("authorization", "")
        scheme, separator, ticket = authorization.partition(" ")
        if not separator or scheme.casefold() != "bearer" or not ticket or len(ticket) > 4096:
            bearer_error()
        try:
            payload = serializer.loads(
                ticket.strip(), salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE,
            )
        except (BadSignature, SignatureExpired, ValueError, TypeError):
            bearer_error()
        if not isinstance(payload, dict) or payload.get("scope") != "history:read":
            bearer_error()
        identity = payload.get("identity")
        if mu.enabled:
            if not isinstance(identity, str) or not identity.isdecimal():
                bearer_error()
            version, user = account_version(int(identity))
            if type(payload.get("version")) is not int or not secrets.compare_digest(
                str(payload["version"]), str(version)
            ):
                bearer_error()
            mu.set_context(user)
            return identity
        if identity != "owner":
            bearer_error()
        version, _ = account_version(None)
        if type(payload.get("version")) is not int or not secrets.compare_digest(
            str(payload["version"]), str(version)
        ):
            bearer_error()
        return identity

    @app.get("/api/integrations/history")
    def read_history(request: Request, limit: int = 250, before_id: int = 0,
                     state: str = "all"):
        """Fetch current persisted history on every request, with keyset paging."""
        identity = require_history_bearer(request)
        if not 1 <= limit <= 500 or before_id < 0:
            raise HTTPException(400, "Paginação inválida")
        if state not in ("all", "applied", "discarded"):
            raise HTTPException(400, "Estado inválido")
        conditions = []
        values = []
        if before_id:
            conditions.append("id < %s")
            values.append(before_id)
        if state == "applied":
            conditions.append("lower(trim(estado)) = 'candidatado'")
        elif state == "discarded":
            conditions.append("lower(trim(estado)) IN ('descartado','descartada')")
        clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        with mu.connect(database, connect_timeout=8) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM jh_history" + clause, values)
                total = cur.fetchone()[0]
                cur.execute(
                    """SELECT id,url,normalized_url,empresa,cargo,estado,data,fonte,motivo
                    FROM jh_history""" + clause +
                    " ORDER BY id DESC LIMIT %s",
                    values + [limit + 1],
                )
                rows = cur.fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = []
        for row in rows:
            raw = str(row[5] or "").strip()
            lowered = raw.casefold()
            normalized_state = (
                "applied" if lowered == "candidatado" else
                "discarded" if lowered in ("descartado", "descartada") else "other"
            )
            items.append({
                "id": row[0], "url": row[1], "normalized_url": row[2],
                "company": row[3], "title": row[4],
                "state": normalized_state, "original_state": raw,
                "date": row[6], "source": row[7], "reason": row[8],
            })
        return JSONResponse(
            {"schema_version": 1, "profile": identity,
             "generated_at": datetime.now(timezone.utc).isoformat(),
             "state_filter": state, "total_remaining": total,
             "items": items,
             "next_before_id": rows[-1][0] if has_more and rows else None},
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )
