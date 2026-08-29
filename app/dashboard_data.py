"""
QBR Executive Dashboard - DB-Driven Configuration
==================================================
This module reads configuration from the database to drive the dashboard.
"""

import streamlit as st
import pandas as pd
from sqlalchemy import text

from app.db import SessionLocal


def get_tower_track_hierarchy():
    """Get Tower -> Track hierarchy from database."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 
                t.TowerID,
                t.TowerName,
                tr.TrackID,
                tr.TrackName
            FROM qbr.Tower t
            JOIN qbr.Track tr ON tr.TowerID = t.TowerID
            WHERE t.IsActive = 1 AND tr.IsActive = 1
            ORDER BY t.DisplayOrder, tr.DisplayOrder
        """)).fetchall()
        
        hierarchy = {}
        for row in result:
            tower_name = row[1]
            track_name = row[3]
            if tower_name not in hierarchy:
                hierarchy[tower_name] = []
            hierarchy[tower_name].append(track_name)
        
        return hierarchy
    finally:
        db.close()


def get_dashboard_kpis():
    """Get KPI configuration from database."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT KPIName, KPICategory, DisplayOrder, Icon, ColorCode
            FROM qbr.DashboardKPI
            WHERE IsActive = 1
            ORDER BY DisplayOrder
        """)).fetchall()
        
        return [
            {
                'name': row[0],
                'category': row[1],
                'order': row[2],
                'icon': row[3],
                'color': row[4]
            }
            for row in result
        ]
    finally:
        db.close()


def get_executive_kpis(start_date=None, end_date=None, tower_id=None, track_id=None):
    """Get executive KPIs from database."""
    db = SessionLocal()
    try:
        query = """
            SELECT
                COUNT(*) AS TotalTickets,
                SUM(CASE WHEN TicketType = 'Parent' THEN 1 ELSE 0 END) AS ParentTickets,
                SUM(CASE WHEN TicketType = 'Child' THEN 1 ELSE 0 END) AS ChildTickets,
                SUM(CASE WHEN State = 'Closed' THEN 1 ELSE 0 END) AS ClosedTickets,
                SUM(CASE WHEN Priority = '1 - Critical' THEN 1 ELSE 0 END) AS CriticalTickets,
                SUM(CASE WHEN Priority = '2 - High' THEN 1 ELSE 0 END) AS HighTickets,
                SUM(CASE WHEN Priority = '3 - Moderate' THEN 1 ELSE 0 END) AS ModerateTickets
            FROM qbr.Ticket
            WHERE (:start_date IS NULL OR OpenedAt >= :start_date)
              AND (:end_date IS NULL OR OpenedAt <= :end_date)
              AND (:tower_id IS NULL OR TowerID = :tower_id)
              AND (:track_id IS NULL OR TrackID = :track_id)
        """
        
        result = db.execute(text(query), {
            'start_date': start_date,
            'end_date': end_date,
            'tower_id': tower_id,
            'track_id': track_id
        }).fetchone()
        
        return {
            'total': result[0] or 0,
            'parents': result[1] or 0,
            'children': result[2] or 0,
            'closed': result[3] or 0,
            'critical': result[4] or 0,
            'high': result[5] or 0,
            'moderate': result[6] or 0
        }
    finally:
        db.close()


def get_tower_track_volume(start_date=None, end_date=None, tower_id=None, track_id=None):
    """Get Tower/Track volume with optional date filtering."""
    db = SessionLocal()
    try:
        query = """
            SELECT 
                t.TowerName, 
                tr.TrackName, 
                COUNT(tk.TicketKey) AS TotalTickets,
                SUM(CASE WHEN tk.TicketType = 'Parent' THEN 1 ELSE 0 END) AS ParentTickets,
                SUM(CASE WHEN tk.TicketType = 'Child' THEN 1 ELSE 0 END) AS ChildTickets,
                SUM(CASE WHEN tk.Priority = '1 - Critical' THEN 1 ELSE 0 END) AS CriticalTickets,
                SUM(CASE WHEN tk.Priority = '2 - High' THEN 1 ELSE 0 END) AS HighTickets,
                SUM(CASE WHEN tk.State = 'Closed' THEN 1 ELSE 0 END) AS ClosedTickets,
                SUM(CASE WHEN tk.State = 'Open' OR tk.ClosedAt IS NULL THEN 1 ELSE 0 END) AS OpenTickets
            FROM qbr.Tower t
            JOIN qbr.Track tr ON tr.TowerID = t.TowerID
            LEFT JOIN qbr.Ticket tk ON tk.TrackID = tr.TrackID
                AND (:start_date IS NULL OR tk.OpenedAt >= :start_date)
                AND (:end_date IS NULL OR tk.OpenedAt <= :end_date)
                AND (:tk_tower_id IS NULL OR tk.TowerID = :tk_tower_id)
                AND (:tk_track_id IS NULL OR tk.TrackID = :tk_track_id)
            GROUP BY t.TowerName, tr.TrackName
            ORDER BY TotalTickets DESC
        """
        
        result = db.execute(text(query), {
            'start_date': start_date,
            'end_date': end_date,
            'tk_tower_id': tower_id,
            'tk_track_id': track_id
        }).fetchall()
        
        data = []
        for row in result:
            data.append({
                'Tower': row[0],
                'Track': row[1],
                'Total': row[2],
                'Parents': row[3],
                'Children': row[4],
                'Critical': row[5],
                'High': row[6],
                'Closed': row[7],
                'Open': row[8]
            })
        
        return pd.DataFrame(data)
    finally:
        db.close()


def get_daily_trend(start_date=None, end_date=None, tower_id=None, track_id=None):
    """Get daily ticket trend from database."""
    db = SessionLocal()
    try:
        query = """
            SELECT 
                CAST(OpenedAt AS DATE) AS TicketDate,
                COUNT(*) AS TotalTickets,
                SUM(CASE WHEN TicketType = 'Parent' THEN 1 ELSE 0 END) AS Parents,
                SUM(CASE WHEN TicketType = 'Child' THEN 1 ELSE 0 END) AS Children
            FROM qbr.Ticket
            WHERE OpenedAt IS NOT NULL
              AND (:start_date IS NULL OR OpenedAt >= :start_date)
              AND (:end_date IS NULL OR OpenedAt <= :end_date)
              AND (:tower_id IS NULL OR TowerID = :tower_id)
              AND (:track_id IS NULL OR TrackID = :track_id)
            GROUP BY CAST(OpenedAt AS DATE)
            ORDER BY TicketDate
        """
        
        result = db.execute(text(query), {
            'start_date': start_date,
            'end_date': end_date,
            'tower_id': tower_id,
            'track_id': track_id
        }).fetchall()
        
        data = []
        for row in result:
            data.append({
                'Date': row[0],
                'Total': row[1],
                'Parents': row[2],
                'Children': row[3]
            })
        
        return pd.DataFrame(data)
    finally:
        db.close()


def get_weekly_trend(start_date=None, end_date=None, tower_id=None, track_id=None):
    """Get weekly ticket trend from database."""
    db = SessionLocal()
    try:
        query = """
            SELECT 
                DATEPART(YEAR, OpenedAt) AS Year,
                DATEPART(WEEK, OpenedAt) AS Week,
                DATEADD(WEEK, DATEDIFF(WEEK, 0, OpenedAt), 0) AS WeekStart,
                COUNT(*) AS TotalTickets,
                SUM(CASE WHEN TicketType = 'Parent' THEN 1 ELSE 0 END) AS Parents,
                SUM(CASE WHEN TicketType = 'Child' THEN 1 ELSE 0 END) AS Children
            FROM qbr.Ticket
            WHERE OpenedAt IS NOT NULL
              AND (:start_date IS NULL OR OpenedAt >= :start_date)
              AND (:end_date IS NULL OR OpenedAt <= :end_date)
              AND (:tower_id IS NULL OR TowerID = :tower_id)
              AND (:track_id IS NULL OR TrackID = :track_id)
            GROUP BY DATEPART(YEAR, OpenedAt), DATEPART(WEEK, OpenedAt), DATEADD(WEEK, DATEDIFF(WEEK, 0, OpenedAt), 0)
            ORDER BY Year, Week
        """
        
        result = db.execute(text(query), {
            'start_date': start_date,
            'end_date': end_date,
            'tower_id': tower_id,
            'track_id': track_id
        }).fetchall()
        
        data = []
        for row in result:
            data.append({
                'Week': f"W{row[2].strftime('%Y-%m-%d')} ({row[1]})",
                'Total': row[3],
                'Parents': row[4],
                'Children': row[5]
            })
        
        return pd.DataFrame(data)
    finally:
        db.close()


def get_monthly_trend(start_date=None, end_date=None, tower_id=None, track_id=None):
    """Get monthly ticket trend from database."""
    db = SessionLocal()
    try:
        query = """
            SELECT 
                YEAR(OpenedAt) AS Year,
                MONTH(OpenedAt) AS Month,
                DATENAME(MONTH, OpenedAt) AS MonthName,
                COUNT(*) AS TotalTickets,
                SUM(CASE WHEN TicketType = 'Parent' THEN 1 ELSE 0 END) AS Parents,
                SUM(CASE WHEN TicketType = 'Child' THEN 1 ELSE 0 END) AS Children
            FROM qbr.Ticket
            WHERE OpenedAt IS NOT NULL
              AND (:start_date IS NULL OR OpenedAt >= :start_date)
              AND (:end_date IS NULL OR OpenedAt <= :end_date)
              AND (:tower_id IS NULL OR TowerID = :tower_id)
              AND (:track_id IS NULL OR TrackID = :track_id)
            GROUP BY YEAR(OpenedAt), MONTH(OpenedAt), DATENAME(MONTH, OpenedAt)
            ORDER BY Year, Month
        """
        
        result = db.execute(text(query), {
            'start_date': start_date,
            'end_date': end_date,
            'tower_id': tower_id,
            'track_id': track_id
        }).fetchall()
        
        data = []
        for row in result:
            data.append({
                'Month': f"{row[2]} {row[0]}",
                'Total': row[3],
                'Parents': row[4],
                'Children': row[5]
            })
        
        return pd.DataFrame(data)
    finally:
        db.close()


def get_quarterly_trend(start_date=None, end_date=None, tower_id=None, track_id=None):
    """Get quarterly ticket trend from database."""
    db = SessionLocal()
    try:
        query = """
            SELECT 
                YEAR(OpenedAt) AS Year,
                DATEPART(QUARTER, OpenedAt) AS Quarter,
                COUNT(*) AS TotalTickets,
                SUM(CASE WHEN TicketType = 'Parent' THEN 1 ELSE 0 END) AS Parents,
                SUM(CASE WHEN TicketType = 'Child' THEN 1 ELSE 0 END) AS Children
            FROM qbr.Ticket
            WHERE OpenedAt IS NOT NULL
              AND (:start_date IS NULL OR OpenedAt >= :start_date)
              AND (:end_date IS NULL OR OpenedAt <= :end_date)
              AND (:tower_id IS NULL OR TowerID = :tower_id)
              AND (:track_id IS NULL OR TrackID = :track_id)
            GROUP BY YEAR(OpenedAt), DATEPART(QUARTER, OpenedAt)
            ORDER BY Year, Quarter
        """
        
        result = db.execute(text(query), {
            'start_date': start_date,
            'end_date': end_date,
            'tower_id': tower_id,
            'track_id': track_id
        }).fetchall()
        
        data = []
        for row in result:
            data.append({
                'Quarter': f"Q{row[1]} {row[0]}",
                'Total': row[2],
                'Parents': row[3],
                'Children': row[4]
            })
        
        return pd.DataFrame(data)
    finally:
        db.close()


def get_alert_frequency(start_date=None, end_date=None, tower_id=None, track_id=None):
    """Get alert frequency by Part from database."""
    db = SessionLocal()
    try:
        query = """
            SELECT 
                Part,
                AlertType,
                Severity,
                COUNT(*) AS AlertCount
            FROM qbr.Alert
            WHERE (:start_date IS NULL OR AlertTime >= :start_date)
              AND (:end_date IS NULL OR AlertTime <= :end_date)
              AND (:tower_id IS NULL OR TowerID = :tower_id)
              AND (:track_id IS NULL OR TrackID = :track_id)
            GROUP BY Part, AlertType, Severity
            ORDER BY AlertCount DESC
        """
        
        result = db.execute(text(query), {
            'start_date': start_date,
            'end_date': end_date,
            'tower_id': tower_id,
            'track_id': track_id
        }).fetchall()
        
        data = []
        for row in result:
            data.append({
                'Part': row[0],
                'AlertType': row[1],
                'Severity': row[2],
                'Count': row[3]
            })
        
        return pd.DataFrame(data)
    finally:
        db.close()


def get_parent_child_relation(start_date=None, end_date=None, tower_id=None, track_id=None):
    """Get parent-child relationship from database."""
    db = SessionLocal()
    try:
        # First, get all child tickets with their parent info (even if parent doesn't exist)
        query = """
            SELECT 
                c.TicketNumber AS ChildTicket,
                c.ParentTicketNumber AS ParentTicket,
                t.TowerName,
                tr.TrackName,
                c.Priority,
                c.State,
                CASE WHEN p.TicketNumber IS NOT NULL THEN 1 ELSE 0 END AS ParentExists
            FROM qbr.Ticket c
            LEFT JOIN qbr.Tower t ON t.TowerID = c.TowerID
            LEFT JOIN qbr.Track tr ON tr.TrackID = c.TrackID
            LEFT JOIN qbr.Ticket p ON p.TicketNumber = c.ParentTicketNumber
            WHERE c.TicketType = 'Child'
              AND (:start_date IS NULL OR c.OpenedAt >= :start_date)
              AND (:end_date IS NULL OR c.OpenedAt <= :end_date)
              AND (:tower_id IS NULL OR c.TowerID = :tower_id)
              AND (:track_id IS NULL OR c.TrackID = :track_id)
            ORDER BY c.ParentTicketNumber
        """
        
        result = db.execute(text(query), {
            'start_date': start_date,
            'end_date': end_date,
            'tower_id': tower_id,
            'track_id': track_id
        }).fetchall()
        
        data = []
        for row in result:
            data.append({
                'ChildTicket': row[0],
                'ParentTicket': row[1],
                'Tower': row[2],
                'Track': row[3],
                'Priority': row[4],
                'State': row[5],
                'ParentExists': 'Yes' if row[6] == 1 else 'No'
            })
        
        # Also get parent tickets with child count
        query2 = """
            SELECT 
                p.TicketNumber AS ParentTicket,
                t.TowerName,
                tr.TrackName,
                p.Priority,
                p.State,
                (SELECT COUNT(*) FROM qbr.Ticket c WHERE c.ParentTicketNumber = p.TicketNumber) AS ChildCount
            FROM qbr.Ticket p
            LEFT JOIN qbr.Tower t ON t.TowerID = p.TowerID
            LEFT JOIN qbr.Track tr ON tr.TrackID = p.TrackID
            WHERE p.TicketType = 'Parent'
              AND (:start_date IS NULL OR p.OpenedAt >= :start_date)
              AND (:end_date IS NULL OR p.OpenedAt <= :end_date)
              AND (:tower_id IS NULL OR p.TowerID = :tower_id)
              AND (:track_id IS NULL OR p.TrackID = :track_id)
            ORDER BY ChildCount DESC
        """
        
        result2 = db.execute(text(query2), {
            'start_date': start_date,
            'end_date': end_date,
            'tower_id': tower_id,
            'track_id': track_id
        }).fetchall()
        
        data2 = []
        for row in result2:
            data2.append({
                'ParentTicket': row[0],
                'Tower': row[1],
                'Track': row[2],
                'Priority': row[3],
                'State': row[4],
                'ChildCount': row[5]
            })
        
        # Return both dataframes as a tuple
        return pd.DataFrame(data2), pd.DataFrame(data)
    finally:
        db.close()


def get_volume_stats(start_date=None, end_date=None, tower_id=None, track_id=None):
    """Get max/min ticket volume statistics."""
    db = SessionLocal()
    try:
        query = """
            WITH DailyCounts AS (
                SELECT
                    CAST(OpenedAt AS DATE) AS TicketDate,
                    DATENAME(WEEKDAY, OpenedAt) AS DayOfWeek,
                    COUNT(*) AS DailyTotal
                FROM qbr.Ticket
                WHERE OpenedAt IS NOT NULL
                  AND (:start_date IS NULL OR OpenedAt >= :start_date)
                  AND (:end_date IS NULL OR OpenedAt <= :end_date)
                  AND (:tower_id IS NULL OR TowerID = :tower_id)
                  AND (:track_id IS NULL OR TrackID = :track_id)
                GROUP BY CAST(OpenedAt AS DATE), DATENAME(WEEKDAY, OpenedAt)
            )
            SELECT 
                (SELECT TOP 1 TicketDate FROM DailyCounts ORDER BY DailyTotal DESC) AS MaxDate,
                (SELECT TOP 1 DayOfWeek FROM DailyCounts ORDER BY DailyTotal DESC) AS MaxDay,
                (SELECT TOP 1 DailyTotal FROM DailyCounts ORDER BY DailyTotal DESC) AS MaxCount,
                (SELECT TOP 1 TicketDate FROM DailyCounts ORDER BY DailyTotal ASC) AS MinDate,
                (SELECT TOP 1 DayOfWeek FROM DailyCounts ORDER BY DailyTotal ASC) AS MinDay,
                (SELECT TOP 1 DailyTotal FROM DailyCounts ORDER BY DailyTotal ASC) AS MinCount,
                (SELECT AVG(DailyTotal * 1.0) FROM DailyCounts) AS AvgCount
            FROM DailyCounts
        """
        
        result = db.execute(text(query), {
            'start_date': start_date,
            'end_date': end_date,
            'tower_id': tower_id,
            'track_id': track_id
        }).fetchone()
        
        if result and result[0]:
            return {
                'max_date': result[0],
                'max_day': result[1],
                'max_count': result[2],
                'min_date': result[3],
                'min_day': result[4],
                'min_count': result[5],
                'avg_count': round(result[6], 1) if result[6] else 0
            }
        return None
    finally:
        db.close()


def get_tower_track_alerts(start_date=None, end_date=None):
    """Get Tower/Track alert summary with optional date filtering."""
    db = SessionLocal()
    try:
        query = """
            SELECT 
                t.TowerName, 
                tr.TrackName, 
                COUNT(a.AlertKey) AS TotalAlerts,
                SUM(CASE WHEN a.Severity = 'Critical' THEN 1 ELSE 0 END) AS CriticalAlerts,
                SUM(CASE WHEN a.Severity = 'High' THEN 1 ELSE 0 END) AS HighAlerts,
                SUM(CASE WHEN a.Severity = 'Moderate' THEN 1 ELSE 0 END) AS ModerateAlerts
            FROM qbr.Tower t
            JOIN qbr.Track tr ON tr.TowerID = t.TowerID
            LEFT JOIN qbr.Alert a ON a.TrackID = tr.TrackID
                AND (:start_date IS NULL OR a.AlertTime >= :start_date)
                AND (:end_date IS NULL OR a.AlertTime <= :end_date)
            GROUP BY t.TowerName, tr.TrackName
            ORDER BY TotalAlerts DESC
        """
        
        result = db.execute(text(query), {
            'start_date': start_date,
            'end_date': end_date
        }).fetchall()
        
        data = []
        for row in result:
            data.append({
                'Tower': row[0],
                'Track': row[1],
                'TotalAlerts': row[2],
                'Critical': row[3],
                'High': row[4],
                'Moderate': row[5]
            })
        
        return pd.DataFrame(data)
    finally:
        db.close()
