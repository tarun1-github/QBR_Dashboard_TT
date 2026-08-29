"""Quick test to verify dashboard data access."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

print('Testing DB-Driven Dashboard...')
print()

from app.dashboard_data import (
    get_tower_track_hierarchy,
    get_executive_kpis,
    get_tower_track_volume,
    get_daily_trend,
    get_volume_stats,
    get_tower_track_alerts,
)
print('[OK] dashboard_data.py imported')

hierarchy = get_tower_track_hierarchy()
print(f'[OK] Tower/Track hierarchy: {len(hierarchy)} towers')
for tower, tracks in hierarchy.items():
    print(f'     {tower}: {len(tracks)} tracks')

kpis = get_executive_kpis()
total = kpis['total']
parents = kpis['parents']
children = kpis['children']
print(f'[OK] Executive KPIs:')
print(f'     Total: {total}, Parents: {parents}, Children: {children}')

volume = get_tower_track_volume()
print(f'[OK] Tower/Track volume: {len(volume)} rows')

daily = get_daily_trend()
print(f'[OK] Daily trend: {len(daily)} days')

stats = get_volume_stats()
if stats:
    max_count = stats['max_count']
    max_day = stats['max_day']
    min_count = stats['min_count']
    min_day = stats['min_day']
    print(f'[OK] Volume stats: Max={max_count} on {max_day}, Min={min_count} on {min_day}')

alerts = get_tower_track_alerts()
print(f'[OK] Tower/Track alerts: {len(alerts)} rows')

print()
print('=' * 50)
print('DASHBOARD READY TO USE!')
print('=' * 50)
print()
print('Run: streamlit run app/dashboard.py')
