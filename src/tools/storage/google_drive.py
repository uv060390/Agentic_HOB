"""
src/tools/storage/google_drive.py  (AM-101)

Creative Library — Google Drive integration for storing creative assets
with performance metadata.

Files are stored in Google Drive; metadata is stored in the
`creative_library` Supabase/Postgres table.

Credentials are fetched from Infisical at runtime:
  /shared/google_drive_service_account  — JSON service account key

For Week 2.5 this is a stub: all operations log and return mock data.
Real Google Drive API wiring is done in Week 3.

Never call this module from a cross-brand context — brand_slug is always
passed explicitly and must match the calling agent's company_id.
"""

from __future__ import annotations

import logging
import uuid as _uuid
from typing import Any

logger = logging.getLogger(__name__)


async def save_creative(
    brand_slug: str,
    file_name: str,
    content: str | bytes,
    metadata: dict[str, Any],
    *,
    created_by_agent: str,
    workflow_run_id: str | None = None,
) -> str:
    """
    Save a creative asset to Google Drive and record metadata in creative_library.

    Returns the Google Drive file URL.

    Args:
        brand_slug:       Brand this creative belongs to (scope enforcement).
        file_name:        File name to store in Drive (e.g. "aim_hook_v1.md").
        content:          File content — text brief or binary image data.
        metadata:         Dict conforming to creative_library schema.
        created_by_agent: Agent slug that produced this creative.
        workflow_run_id:  Workflow run that produced this (nullable).

    Raises:
        CreativeLibraryError: if Drive upload or DB write fails.
    """
    creative_id = metadata.get("creative_id") or str(_uuid.uuid4())
    mock_url = f"https://drive.google.com/mock/{brand_slug}/{creative_id}/{file_name}"

    logger.info(
        "CreativeLibrary.save | brand=%s file=%s creative_id=%s agent=%s workflow=%s",
        brand_slug, file_name, creative_id, created_by_agent, workflow_run_id,
    )

    # TODO (Week 3): Replace stub with real Google Drive API upload
    # from googleapiclient.discovery import build
    # creds_json = get_secret("/shared/google_drive_service_account")
    # creds = service_account.Credentials.from_service_account_info(json.loads(creds_json))
    # service = build("drive", "v3", credentials=creds)
    # ... upload file, get real URL ...

    # TODO (Week 3): INSERT into creative_library table via Supabase/SQLAlchemy
    # record = {creative_id, brand_slug, source, competitor_brand, predicted_ctr,
    #           actual_ctr=None, creative_type, file_url=mock_url,
    #           created_by_agent, workflow_run_id}

    return mock_url


async def get_top_creatives(
    brand_slug: str,
    limit: int = 10,
    sort_by: str = "predicted_ctr",
    source: str | None = None,
) -> list[dict[str, Any]]:
    """
    Retrieve top-performing creatives from the Creative Library.

    Args:
        brand_slug: Brand to query — never cross-brand.
        limit:      Max results.
        sort_by:    "predicted_ctr" | "actual_ctr" | "created_at"
        source:     Filter by "competitor" | "original" | None (all).

    Returns list of creative metadata dicts (creative_library schema).
    """
    logger.info(
        "CreativeLibrary.get_top | brand=%s limit=%d sort=%s source=%s",
        brand_slug, limit, sort_by, source,
    )

    # TODO (Week 3): Replace with real Supabase query:
    # SELECT * FROM creative_library
    # WHERE brand_slug = :brand_slug
    #   AND (:source IS NULL OR source = :source)
    # ORDER BY {sort_by} DESC NULLS LAST
    # LIMIT :limit

    effective_source = source or "competitor"
    return [
        {
            "creative_id": f"mock-creative-{i}",
            "brand_slug": brand_slug,
            "source": effective_source,
            "competitor_brand": "mock_competitor" if effective_source == "competitor" else None,
            "predicted_ctr": round(0.038 - i * 0.003, 4),
            "actual_ctr": None,
            "creative_type": "image",
            "file_url": f"https://drive.google.com/mock/{brand_slug}/creative-{i}",
            "created_by_agent": "aim-scout",
            "workflow_run_id": None,
        }
        for i in range(min(limit, 5))
    ]


async def update_actual_ctr(
    creative_id: str,
    actual_ctr: float,
    *,
    updated_by_agent: str,
) -> None:
    """
    Retroactively update actual CTR for a creative once measured by the Performance agent.

    Called by Performance agent during daily_performance_check.
    This is the feedback loop that makes the Creative Library a learning asset.
    """
    logger.info(
        "CreativeLibrary.update_ctr | creative_id=%s actual_ctr=%.4f agent=%s",
        creative_id, actual_ctr, updated_by_agent,
    )

    # TODO (Week 3): UPDATE creative_library
    # SET actual_ctr = :actual_ctr, updated_at = now()
    # WHERE id = :creative_id
