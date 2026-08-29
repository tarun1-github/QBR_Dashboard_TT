"""QBR dashboard package compatibility and hierarchy resolver patch."""

# Keep the existing analytics module intact, but override its runtime hierarchy
# resolver so existing rows with missing TowerID/TrackID are resolved from the
# ServiceNow AssignmentGroup and the reference Tower/Track catalogue.
try:
    from app import dashboard_data as _dd

    def _resolved_ticket_context(db, alias="tk"):
        cols = _dd._columns(db, "Ticket")
        joins = ""
        has_tower = "TowerID" in cols and _dd._table_exists(db, "Tower")
        has_track = "TrackID" in cols and _dd._table_exists(db, "Track")
        has_tt = "TowerTrackID" in cols and _dd._table_exists(db, "TowerTrack")

        if has_tower:
            joins += f" LEFT JOIN qbr.Tower t ON t.TowerID={alias}.TowerID"
        if has_track:
            joins += f" LEFT JOIN qbr.Track tr ON tr.TrackID={alias}.TrackID"
        if has_tt:
            joins += f" LEFT JOIN qbr.TowerTrack tt ON tt.TowerTrackID={alias}.TowerTrackID"

        # Resolve missing FK values from AssignmentGroup without multiplying
        # ticket rows. The catalogue match is preferred; explicit patterns cover
        # ServiceNow groups whose names differ from the friendly TrackName.
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
        tower_fallback = (
            f"CASE WHEN UPPER(COALESCE({ag},'')) LIKE '%FN-SFNOC%' "
            f"OR UPPER(COALESCE({ag},'')) LIKE '%FN-THD%' "
            f"OR UPPER(COALESCE({ag},'')) LIKE '%HSBC-DATA%' "
            f"OR UPPER(COALESCE({ag},'')) LIKE '%JLK%' "
            f"THEN COALESCE(agtr.TowerName,'Foundation') ELSE NULL END"
        )
        track_fallback = (
            f"CASE WHEN UPPER(COALESCE({ag},'')) LIKE '%FN-SFNOC%' THEN 'SFNOC' "
            f"WHEN UPPER(COALESCE({ag},'')) LIKE '%FN-THD%' OR UPPER(COALESCE({ag},'')) LIKE '%JLK%' THEN 'THD Data' "
            f"WHEN UPPER(COALESCE({ag},'')) LIKE '%HSBC-DATA%' THEN 'HSBC Data' ELSE NULL END"
        )

        tower_parts = []
        track_parts = []
        if has_tower:
            tower_parts.append("t.TowerName")
        if has_tt:
            tower_parts.append("tt.TowerName")
        if has_catalogue:
            tower_parts.append("agtr.TowerName")
        if "ProjectName" in cols:
            tower_parts.append(f"NULLIF(NULLIF(LTRIM(RTRIM({alias}.ProjectName)),''),'Unknown')")
        tower_parts.append(tower_fallback)

        if has_track:
            track_parts.append("tr.TrackName")
        if has_tt:
            track_parts.append("tt.TrackName")
        if has_catalogue:
            track_parts.append("agtr.TrackName")
        if "TrackName" in cols:
            track_parts.append(f"NULLIF(NULLIF(LTRIM(RTRIM({alias}.TrackName)),''),'Unknown')")
        track_parts.append(track_fallback)

        tower_expr = "COALESCE(" + ",".join(tower_parts) + ",'Unknown')"
        track_expr = "COALESCE(" + ",".join(track_parts) + ",'Unknown')"
        scope = f"(:tower IS NULL OR {tower_expr}=:tower) AND (:track IS NULL OR {track_expr}=:track)"
        return cols, joins, tower_expr, track_expr, scope

    _dd._ticket_context = _resolved_ticket_context

    # Normalize the public alert result to Device even when an older DB/query
    # shape exposes the physical column as Part.
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
    # Do not prevent the dashboard from starting if the analytics module cannot
    # be imported during a lightweight CLI operation.
    pass
