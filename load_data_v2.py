"""QBR ServiceNow loader v2.

Reads XLSX/CSV/TXT from app/dataset, de-duplicates TicketNumber before DB load,
uses qbr.Customer for CompanyAccount -> Tower -> Track, normalizes Home* to
Home Depot, stores Caller and Device, and derives qbr.Alert rows from tickets
whose Caller is EMS or CMSP. Source files are archived only after a successful
transaction.
"""
from __future__ import annotations
import shutil
from datetime import datetime
from pathlib import Path
import pandas as pd
from sqlalchemy import text
from app.db import SessionLocal

ROOT=Path(__file__).resolve().parent
DATASET=ROOT/"app"/"dataset"
EXT={".xlsx",".xls",".csv",".txt"}
GENERATED={"_merged_input.xlsx","_duplicate_records.xlsx"}

def norm(v):
    if v is None or pd.isna(v): return ""
    s=str(v).strip()
    return "" if s.lower() in {"","nan","none","null","nat"} else s

def key(v):
    s=norm(v)
    if s.endswith(".0") and s[:-2].isdigit(): s=s[:-2]
    return s.upper()

def first(row,names):
    cols={str(c).strip().lower():c for c in row.index}
    for n in names:
        c=cols.get(n.lower())
        if c is not None:
            v=norm(row.get(c))
            if v:return v
    return None

def dt(row,names):
    v=first(row,names)
    if not v:return None
    try:return pd.to_datetime(v).to_pydatetime()
    except Exception:return None

def company(v):
    s=norm(v)
    return "Home Depot" if "home" in s.lower() else s

def read_file(p):
    if p.suffix.lower() in {".xlsx",".xls"}: df=pd.read_excel(p,dtype=object)
    elif p.suffix.lower()==".csv": df=pd.read_csv(p,dtype=object)
    else:
        try: df=pd.read_csv(p,sep="\t",dtype=object)
        except Exception: df=pd.read_csv(p,dtype=object)
    df.columns=[str(c).replace("\ufeff","").strip() for c in df.columns]
    return df

def discover(folder,single=None):
    if single:
        p=Path(single)
        if not p.exists():p=folder/p.name
        if not p.exists():raise FileNotFoundError(single)
        return [p]
    return sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in EXT and p.name not in GENERATED and not p.name.startswith("_")],key=lambda p:p.name.lower())

def ticket_col(cols):
    aliases=["TicketNumber","Number","Incident Number","IncidentNumber","Ticket Number","Ticket_Number","Incident_Number"]
    lookup={str(c).strip().lower():c for c in cols}
    return next((lookup[a.lower()] for a in aliases if a.lower() in lookup),None)

def merge_inputs(files,folder):
    frames=[]
    for p in files:
        df=read_file(p)
        if df.empty:continue
        tc=ticket_col(df.columns)
        if not tc:raise RuntimeError(f"{p.name}: TicketNumber/Number column not found")
        df["SourceFile"]=p.name
        df["_TicketKey"]=df[tc].map(key)
        frames.append(df)
    if not frames:return None,None,0,0
    all_df=pd.concat(frames,ignore_index=True,sort=False)
    valid=all_df["_TicketKey"].ne("")
    counts=all_df.loc[valid,"_TicketKey"].value_counts()
    dup_keys=set(counts[counts>1].index)
    dup=all_df[all_df["_TicketKey"].isin(dup_keys)].copy()
    if not dup.empty:
        dup["DuplicateCount"]=dup.groupby("_TicketKey")["_TicketKey"].transform("size")
        dup["DuplicateSources"]=dup.groupby("_TicketKey")["SourceFile"].transform("nunique")
        dup["DuplicateType"]=dup["DuplicateSources"].map(lambda n:"Across files" if n>1 else "Within file")
    dup_path=folder/"_duplicate_records.xlsx"
    with pd.ExcelWriter(dup_path,engine="openpyxl") as w:
        dup.to_excel(w,sheet_name="Duplicates",index=False)
        summary=(dup.groupby("_TicketKey",as_index=False).agg(Occurrences=("_TicketKey","size"),SourceFiles=("SourceFile",lambda s:" | ".join(dict.fromkeys(s)))) if not dup.empty else pd.DataFrame(columns=["_TicketKey","Occurrences","SourceFiles"]))
        summary.to_excel(w,sheet_name="Summary",index=False)
    rows=[]
    for _,g in all_df[valid].groupby("_TicketKey",sort=False):
        if len(g)==1: rows.append(g.iloc[0].drop(labels=["_TicketKey"]).to_dict());continue
        g=g.copy();g["_priority"]=g.SourceFile.map(lambda s:30 if any(x in str(s).lower() for x in ("closed","resolved","complete")) else 20 if any(x in str(s).lower() for x in ("updated","update","current")) else 10);g=g.sort_values("_priority",ascending=False)
        out={}
        for c in g.columns:
            if c in {"_TicketKey","_priority"}:continue
            vals=[v for v in g[c].tolist() if norm(v)]
            out[c]=vals[0] if vals else None
        out["SourceFile"]=" | ".join(dict.fromkeys(str(x) for x in g.SourceFile.tolist()));rows.append(out)
    merged=pd.DataFrame(rows)
    tc=ticket_col(merged.columns)
    if tc is None or merged[tc].map(key).duplicated().any():raise RuntimeError("Duplicate TicketNumber remains after merge")
    merged_path=folder/"_merged_input.xlsx";merged.to_excel(merged_path,index=False)
    print(f"Input rows: {len(all_df):,}; unique load rows: {len(merged):,}; duplicate occurrences: {len(dup):,}")
    return merged,dup_path,len(dup),len(merged)

def mappings(db):
    customers={key(r["CompanyAccountName"] or r["CustomerName"]):r for r in db.execute(text("SELECT c.CustomerID,c.CompanyAccountName,c.CustomerName,c.TowerID,c.TrackID,tw.TowerName,tr.TrackName FROM qbr.Customer c LEFT JOIN qbr.Tower tw ON tw.TowerID=c.TowerID LEFT JOIN qbr.Track tr ON tr.TrackID=c.TrackID WHERE ISNULL(c.IsActive,1)=1")).mappings().all()}
    tracks={key(r["TrackName"]):r for r in db.execute(text("SELECT tr.TrackID,tr.TowerID,tr.TrackName,tw.TowerName FROM qbr.Track tr JOIN qbr.Tower tw ON tw.TowerID=tr.TowerID WHERE ISNULL(tr.IsActive,1)=1")).mappings().all()}
    return customers,tracks

def resolve(row,customers,tracks):
    ca=company(first(row,["Company account","CompanyAccount","Company","Customer"]))
    c=customers.get(key(ca)) if ca else None
    if c:return ca,c.CustomerID,c.TowerID,c.TrackID,c.TowerName,c.TrackName
    tr=first(row,["TrackName","Track"]);r=tracks.get(key(tr)) if tr else None
    if r:return ca,None,r.TowerID,r.TrackID,r.TowerName,r.TrackName
    return ca,None,None,None,None,None

def load(merged,db,replace):
    customers,tracks=mappings(db);batch=db.execute(text("SELECT NEWID()")).scalar();seen=set();loaded=alerts=skipped=0;errors=[]
    ticket_sql=text("""INSERT INTO qbr.Ticket(TicketNumber,ParentTicketNumber,TicketType,CustomerID,TowerID,TrackID,AssignmentGroup,CompanyAccount,ConfigurationItem,Service,Device,Caller,Priority,State,Impact,ShortDescription,OpenedAt,CreatedAt,UpdatedAt,ClosedAt,CandidateForVE,VETimeSavedMinutes,ResolutionCode,CauseCode,SourceFile,LoadBatchID,LoadedAt,IsMonitoringGenerated) VALUES(:tn,:parent,:type,:cid,:tower,:track,:ag,:company,:ci,:service,:device,:caller,:priority,:state,:impact,:short_desc,:opened,:created,:updated,:closed,:ve,:ve_minutes,:resolution,:cause,:source,:batch,SYSUTCDATETIME(),:monitoring)""")
    alert_sql=text("""INSERT INTO qbr.Alert(AlertID,TicketNumber,CustomerID,TowerID,TrackID,AlertTime,Service,Device,AlertType,Severity,MonitoringTool,AlertDescription,SourceFile,LoadBatchID,LoadedAt,Caller) VALUES(:aid,:tn,:cid,:tower,:track,:at,:service,:device,:atype,:severity,:tool,:description,:source,:batch,SYSUTCDATETIME(),:caller)""")
    try:
        for i,row in merged.iterrows():
            try:
                tn=first(row,["Number","TicketNumber","Ticket_Number","Incident Number","IncidentNumber","Ticket Number"]);tk=key(tn)
                if not tk or tk in seen:skipped+=1;continue
                seen.add(tk);ca,cid,tower,track,_,_=resolve(row,customers,tracks)
                parent=first(row,["Parent Incident","ParentIncident","Parent_Incident","ParentTicketNumber","Parent"]);caller=first(row,["Caller","caller"]);monitoring=key(caller) in {"EMS","CMSP"};opened=dt(row,["Opened","OpenedAt","Opened_At"]);created=dt(row,["Created","CreatedAt","Created_Date"]) or opened;updated=dt(row,["Updated","UpdatedAt","Updated_Date"]);closed=dt(row,["Closed","ClosedAt","Closed_At","Resolved","ResolvedAt"])
                device=first(row,["Device","device","Part","part"]);service=first(row,["Service","service"]);assignment=first(row,["Assignment group","AssignmentGroup","Assignment_Group"]);short=first(row,["Short description","ShortDescription","Short_Description","Description"]);short=short[:500] if short else None
                exists=db.execute(text("SELECT 1 FROM qbr.Ticket WHERE TicketNumber=:tn"),{"tn":tn}).first()
                if exists and not replace:skipped+=1;continue
                db.execute(ticket_sql,{"tn":tn,"parent":parent,"type":"Child" if parent else "Parent","cid":cid,"tower":tower,"track":track,"ag":assignment,"company":ca,"ci":first(row,["Configuration item","ConfigurationItem","Configuration_Item","CI"]),"service":service,"device":device,"caller":caller,"priority":first(row,["Priority","priority"]),"state":first(row,["State","Status","state","status"]),"impact":first(row,["Impact","impact"]),"short_desc":short,"opened":opened,"created":created,"updated":updated,"closed":closed,"ve":first(row,["Candidate for VE","CandidateForVE"]),"ve_minutes":None,"resolution":first(row,["Resolution code","ResolutionCode","Resolution"]),"cause":first(row,["Cause code","CauseCode","Cause"]),"source":str(row.get("SourceFile") or ""),"batch":batch,"monitoring":monitoring});loaded+=1
                if monitoring:
                    aid=first(row,["AlertID","Alert ID","Alert_Number"]) or f"TICKET-{tk}"
                    if db.execute(text("SELECT 1 FROM qbr.Alert WHERE AlertID=:aid"),{"aid":aid}).first():aid=f"{aid}-{tk}"
                    db.execute(alert_sql,{"aid":aid,"tn":tn,"cid":cid,"tower":tower,"track":track,"at":opened or created or datetime.now(),"service":service,"device":device,"atype":first(row,["AlertType","Alert Type","Type"]) or "Monitoring-generated ticket","severity":first(row,["Priority","priority"]),"tool":caller,"description":short,"source":str(row.get("SourceFile") or ""),"batch":batch,"caller":caller});alerts+=1
            except Exception as exc:errors.append(f"row {i+1}: {exc}")
        if errors:db.rollback();return 0,0,len(errors),skipped
        dup=db.execute(text("SELECT TOP 1 TicketNumber FROM qbr.Ticket WHERE LoadBatchID=:b GROUP BY TicketNumber HAVING COUNT(*)>1"),{"b":batch}).first()
        if dup:db.rollback();return 0,0,1,skipped
        db.commit();return loaded,alerts,0,skipped
    except Exception:db.rollback();raise

def archive(paths,folder):
    dest=folder/"processed"/datetime.now().strftime("%Y%m%d_%H%M%S");dest.mkdir(parents=True,exist_ok=True);moved=[]
    for p in paths:
        p=Path(p)
        if p.exists():shutil.move(str(p),str(dest/p.name));moved.append(p.name)
    return dest,moved

def main():
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument("--file");ap.add_argument("--replace-tickets","--clear",dest="replace",action="store_true");ap.add_argument("--dataset-folder",default=str(DATASET));a=ap.parse_args();folder=Path(a.dataset_folder);files=discover(folder,a.file)
    if not files:print(f"No source files found in {folder}");return
    merged,dup,dup_rows,merged_rows=merge_inputs(files,folder)
    if merged is None:return
    db=SessionLocal()
    try:
        if a.replace:db.execute(text("DELETE FROM qbr.Ticket"));db.execute(text("DELETE FROM qbr.Alert"))
        loaded,alerts,errors,skipped=load(merged,db,a.replace)
        if errors:print(f"LOAD FAILED; transaction rolled back. Errors: {errors}");return
        dest,moved=archive([*files,dup,folder/"_merged_input.xlsx"],folder)
        print("\nPOST-LOAD FILE CLEANUP");[print(f"  {x} moved successfully") for x in moved];print(f"Moved location: {dest}");print(f"Tickets loaded: {loaded:,}; monitoring alerts: {alerts:,}; duplicates recorded: {dup_rows:,}; merged rows: {merged_rows:,}; skipped: {skipped:,}")
    finally:db.close()
if __name__=="__main__":main()
