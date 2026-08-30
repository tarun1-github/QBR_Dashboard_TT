from pathlib import Path

path = Path(__file__).resolve().parents[1] / "app" / "dashboard.py"
text = path.read_text(encoding="utf-8")

bad = '''    st.divider();allowed=assigned_tracks(uname()) if r=="MANAGER" else []
    tower_options=sorted({x[0] for x in allowed}) if r=="MANAGER" else sorted(hierarchy.keys())
    st.markdown('<div class="qbr-side-head">1️⃣ TOWER</div>',unsafe_allow_html=True);tower=st.selectbox("Tower",["All"]+tower_options,label_visibility="collapsed",key="scope_tower")
    tracks = (
    sorted({str(track_name) for track_list in hierarchy.values() for track_name in track_list})
    if tower == "All"
    else sorted([str(track_name) for track_name in hierarchy.get(tower, [])])
    )
'''

if bad not in text:
    raise SystemExit("Expected duplicate role-manager/sidebar block was not found; no changes made.")

backup = path.with_suffix(path.suffix + ".role-manager-backup")
backup.write_text(text, encoding="utf-8")
path.write_text(text.replace(bad, "", 1), encoding="utf-8")
print(f"Fixed: {path}")
print(f"Backup: {backup}")
