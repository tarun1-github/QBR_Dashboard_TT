from pathlib import Path

path = Path(__file__).resolve().parents[1] / "app" / "dashboard.py"
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
original = list(lines)

# Remove the accidental second sidebar block. Keep the first valid block.
start = next((i for i, line in enumerate(lines) if 'if r=="MANAGER"' in line), None)
if start is not None:
    end = next((i for i in range(start, len(lines)) if '2️⃣ TRACK' in lines[i]), None)
    if end is not None:
        del lines[start:end]

# Remove a duplicated admin Tower/Track/Manager selector line if present.
needle = 'tsel=st.selectbox("Tower",towers,key="admin_tower")'
seen = 0
cleaned = []
for line in lines:
    if needle in line:
        seen += 1
        if seen > 1:
            continue
    cleaned.append(line)
lines = cleaned

if lines == original:
    raise SystemExit("No role-manager merge artifact found; no changes made.")

backup = path.with_suffix(path.suffix + ".role-manager-backup")
backup.write_text("".join(original), encoding="utf-8")
path.write_text("".join(lines), encoding="utf-8")
print(f"Fixed: {path}")
print(f"Backup: {backup}")
