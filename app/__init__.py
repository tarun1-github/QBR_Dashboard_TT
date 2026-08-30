"""QBR dashboard package compatibility and hierarchy resolver patch.

Authoritative hierarchy rule:
    qbr.Ticket.CompanyAccount -> qbr.Customer -> TowerID/TrackID -> Tower/Track.

Existing ticket TowerID/TrackID and AssignmentGroup are only fallbacks. This
prevents the dashboard from showing Unknown -> Unknown when the customer
mapping is already present in qbr.Customer.
"""

try:
    from app import dashboard_data as _dd

    def _normal_account(alias: str) -> str:
        return (
            f"CASE WHEN UPPER(LTRIM(RTRIM(ISNULL({alias}.CompanyAccount,'')))) LIKE '%HOME%' "
            f"THEN 'Home Depot' "
            f"ELSE LTRIM(RTRIM(ISNULL({alias}.CompanyAccount,''))) END"
        )

    def _resolved_ticket_context(db, alias="tk"):
        cols = _dd._columns(db, "Ticket")
        joins = ""

        has_customer = _dd._table_exists(db, "Customer")
        has_tower = "TowerID" in cols and _dd._table_exists(db, "Tower")
        has_track = "TrackID" in cols and _dd._table_exists(db, "Track")
        has_tt = "TowerTrackID" in cols and _dd._table_exists(db, "TowerTrack")

        # Customer is the authoritative CompanyAccount -> Tower/Track map.
        if has_customer:
            joins += (
                f" LEFT JOIN qbr.Customer cust "
                f"ON UPPER(LTRIM(RTRIM(ISNULL(cust.CompanyAccountName,'')))) "
                f"= UPPER({_normal_account(alias)}) "
                f"AND ISNULL(cust.IsActive,1)=1"
            )
            if _dd._table_exists(db, "Tower"):
                joins += " LEFT JOIN qbr.Tower cust_t ON cust_t.TowerID=cust.TowerID AND ISNULL(cust_t.IsActive,1)=1"
            if _dd._table_exists(db, "Track"):
                joins += " LEFT JOIN qbr.Track cust_tr ON cust_tr.TrackID=cust.TrackID AND ISNULL(cust_tr.IsActive,1)=1"

        if has_tower:
            joins += f" LEFT JOIN qbr.Tower t ON t.TowerID={alias}.TowerID"
        if has_track:
            joins += f" LEFT JOIN qbr.Track tr ON tr.TrackID={alias}.TrackID"
        if has_tt:
            joins += f" LEFT JOIN qbr.TowerTrack tt ON tt.TowerTrackID={alias}.TowerTrackID"

        # AssignmentGroup remains a fallback for legacy rows whose Customer
        # mapping is genuinely absent. OUTER APPLY returns at most one row.
        has_catalogue = "AssignmentGroup" in cols and _dd._table_exists(db, "Track") and _dd._table_exists(db, "Tower")
        if has_catalogue:
            joins += f''' OUTER APPLY (
                SELECT TOP 1 tr_ag.TrackName, t_ag.TowerName
                FROM qbr.Track tr_ag
                JOIN qbr.Tower t_ag ON t_ag.TowerID=tr_ag.TowerID
                WHERE ISNULL(tr_ag.IsActive,1)=1
                  AND (
                    UPPER(ISNULL({alias}.AssignmentGroup,'')) LIKE '%' + UPPER(LTRIM(RTRIM(tr_ag.TrackName))) + '%'
                    OR (UPPER(ISNULL({alias}.AssignmentGroup,'')) LIKE '%FN-SFNOC%' AND tr_ag.TrackName='SFNOC')
                    OR (UPPER(ISNULL({alias}.AssignmentGroup,'')) LIKE '%FN-THD%' AND tr_ag.TrackName='THD Data')
                    OR (UPPER(ISNULL({alias}.AssignmentGroup,'')) LIKE '%HSBC-DATA%' AND tr_ag.TrackName='HSBC Data')
                    OR (UPPER(ISNULL({alias}.AssignmentGroup,'')) LIKE '%JLK%' AND tr_ag.TrackName='THD Data')
                  )
                ORDER BY LEN(LTRIM(RTRIM(tr_ag.TrackName))) DESC
            ) agtr'''

        ag = f"NULLIF(LTRIM(RTRIM({alias}.AssignmentGroup)),'')" if "AssignmentGroup" in cols else "NULL"
        ag_upper = f"UPPER(COALESCE({ag},''))"
        tower_fallback = (
            f"CASE WHEN {ag_upper} LIKE '%FN-SFNOC%' "
            f"OR {ag_upper} LIKE '%FN-THD%' "
            f"OR {ag_upper} LIKE '%HSBC-DATA%' "
            f"OR {ag_upper} LIKE '%JLK%' "
            f"THEN COALESCE(agtr.TowerName,'Foundation') ELSE NULL END"
        )
        track_fallback = (
            f"CASE WHEN {ag_upper} LIKE '%FN-SFNOC%' THEN 'SFNOC' "
            f"WHEN {ag_upper} LIKE '%FN-THD%' OR {ag_upper} LIKE '%JLK%' THEN 'THD Data' "
            f"WHEN {ag_upper} LIKE '%HSBC-DATA%' THEN 'HSBC Data' ELSE NULL END"
        )

        # Customer mapping is first. Existing ticket FK values are second.
        # ProjectName is deliberately not used as a Tower.
        tower_parts = []
        track_parts = []
        if has_customer:
            tower_parts.append("NULLIF(LTRIM(RTRIM(cust_t.TowerName)),'')")
            track_parts.append("NULLIF(LTRIM(RTRIM(cust_tr.TrackName)),'')")
        if has_tower:
            tower_parts.append("NULLIF(LTRIM(RTRIM(t.TowerName)),'')")
        if has_tt:
            tower_parts.append("NULLIF(LTRIM(RTRIM(tt.TowerName)),'')")
        if has_track:
            track_parts.append("NULLIF(LTRIM(RTRIM(tr.TrackName)),'')")
        if has_tt:
            track_parts.append("NULLIF(LTRIM(RTRIM(tt.TrackName)),'')")
        if has_catalogue:
            tower_parts.append("NULLIF(LTRIM(RTRIM(agtr.TowerName)),'')")
            track_parts.append("NULLIF(LTRIM(RTRIM(agtr.TrackName)),'')")
        if "TrackName" in cols:
            track_parts.append(f"NULLIF(NULLIF(LTRIM(RTRIM({alias}.TrackName)),''),'Unknown')")
        tower_parts.append(tower_fallback)
        track_parts.append(track_fallback)

        tower_expr = "COALESCE(" + ",".join(tower_parts) + ",'Unknown')"
        track_expr = "COALESCE(" + ",".join(track_parts) + ",'Unknown')"
        scope = f"(:tower IS NULL OR {tower_expr}=:tower) AND (:track IS NULL OR {track_expr}=:track)"
        return cols, joins, tower_expr, track_expr, scope

    _dd._ticket_context = _resolved_ticket_context

    _old_alert_frequency = _dd.get_alert_frequency

    def _device_alert_frequency(*args, **kwargs):
        frame = _old_alert_frequency(*args, **kwargs)
        if "Device" not in frame.columns and "Part" in frame.columns:
            frame = frame.rename(columns={"Part": "Device"})
        for col in ("Device", "AlertType", "Severity", "Count"):
            if col not in frame.columns:
                frame[col] = [] if frame.empty else "Unknown"
        return frame[["Device", "AlertType", "Severity", "Count"]]

    _dd.get_alert_frequency = _device_alert_frequency
except Exception:
    pass
