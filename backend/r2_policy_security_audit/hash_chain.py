import hashlib
import json
import uuid
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from backend.app.db.models import AuditLogModel
from backend.app.scheduler.virtual_clock import clock

GENESIS_HASH = "0" * 64

def calculate_hash(
    prev_hash: str,
    ts: str,
    actor: str,
    event_type: str,
    entity_type: str,
    entity_id: str,
    payload_json: str,
    mandate_version: int
) -> str:
    raw = f"{prev_hash}|{ts}|{actor}|{event_type}|{entity_type}|{entity_id}|{payload_json}|{mandate_version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def append_audit_event(
    db: Session,
    actor: str,
    event_type: str,
    entity_type: str,
    entity_id: str,
    payload: Dict[str, Any],
    mandate_version: int = 1
) -> AuditLogModel:
    latest = db.query(AuditLogModel).order_by(AuditLogModel.seq.desc()).first()
    prev_hash = latest.hash if latest else GENESIS_HASH

    ts = clock.now().isoformat()
    payload_json = json.dumps(payload, sort_keys=True)
    entry_hash = calculate_hash(
        prev_hash=prev_hash,
        ts=ts,
        actor=actor,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload_json=payload_json,
        mandate_version=mandate_version
    )

    entry = AuditLogModel(
        id=str(uuid.uuid4()),
        ts=ts,
        actor=actor,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload_json=payload_json,
        mandate_version=mandate_version,
        prev_hash=prev_hash,
        hash=entry_hash
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

def verify_audit_chain(db: Session) -> Tuple[bool, str, int]:
    entries = db.query(AuditLogModel).order_by(AuditLogModel.seq.asc()).all()
    if not entries:
        return True, "Audit log is empty. Chain valid.", 0

    prev_hash = GENESIS_HASH
    for i, entry in enumerate(entries):
        if entry.prev_hash != prev_hash:
            return False, f"Broken link at row {i} (id: {entry.id}): prev_hash mismatch.", i

        expected_hash = calculate_hash(
            prev_hash=entry.prev_hash,
            ts=entry.ts,
            actor=entry.actor,
            event_type=entry.event_type,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            payload_json=entry.payload_json,
            mandate_version=entry.mandate_version
        )
        if entry.hash != expected_hash:
            return False, f"Tampered hash at row {i} (id: {entry.id}). Computed: {expected_hash}, recorded: {entry.hash}.", i

        prev_hash = entry.hash

    return True, f"Cryptographic integrity verified across {len(entries)} events.", len(entries)
