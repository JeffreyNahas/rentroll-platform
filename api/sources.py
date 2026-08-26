"""Build the `sources` list on a per-response basis.

Sources always point at the *latest* snapshot per (property, report_type)
-- the same rule the gold views apply -- so citations stay consistent with
the numbers they explain.
"""

from __future__ import annotations

from psycopg import Connection

from api.envelope import Source


def build_sources(
    conn: Connection,
    property_codes: list[str] | None = None,
    report_types: list[str] | None = None,
) -> list[Source]:
    """Return one Source per (property, report_type) at the latest snapshot.

    `property_codes=None` (default) returns sources for every property.
    """
    where: list[str] = []
    params: list = []
    if property_codes:
        where.append("p.property_code = ANY(%s)")
        params.append(property_codes)
    if report_types:
        where.append("rs.report_type = ANY(%s)")
        params.append(report_types)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
        SELECT DISTINCT ON (rs.property_id, rs.report_type)
            rs.snapshot_id,
            p.property_code,
            rs.report_type,
            sf.filename,
            rs.as_of_date
        FROM report_snapshot rs
        JOIN property p     ON p.property_id     = rs.property_id
        JOIN source_file sf ON sf.source_file_id = rs.source_file_id
        {where_sql}
        ORDER BY rs.property_id, rs.report_type, rs.as_of_date DESC
    """
    rows = conn.execute(sql, params).fetchall()
    return [
        Source(
            snapshot_id=r["snapshot_id"],
            property_code=r["property_code"],
            report_type=r["report_type"],
            filename=r["filename"],
            as_of_date=r["as_of_date"],
        )
        for r in rows
    ]
