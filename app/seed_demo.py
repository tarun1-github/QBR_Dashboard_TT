from datetime import datetime, timedelta
import random
from .db import SessionLocal
from .init_db import init_db
from .models import Ticket, Alert, TicketAlert, Project

random.seed(7)

PROJECTS = [
("BOA EV","Collab"),("HSBC","Collab"),("Problem Management","Collab"),
("RIL","Non CMS"),("Cybersecurity","Security"),("SFNOC","Foundation"),
("THD","Data Foundation"),("BOA TP","Collab"),("GTM TP","Collab"),
("HD Voice (Bgl)","Collab"),("HSBC Data","Foundation"),("SCNOC","Collab"),
("DC-ACI","Security"),("Infra","Security"),("SOC","Security")
]
PARTS=["CUCM","Unity Connection","CUBE","SBC","Contact Center","Voice Gateway","ESXi","Network","Application","Database"]
SERVICES=["IPT","Contact Center","Voice","Network","Security","Platform"]
ALERTS=["CPU High","Memory High","Service Down","SIP Failure","Registration Failure","Disk Threshold","Interface Down","Process Restart"]

def seed():
    init_db()
    db=SessionLocal()
    try:
        if db.query(Ticket).count()>0:
            print("Demo data already exists.")
            return
        for p,t in PROJECTS:
            db.add(Project(name=p,track=t))
        db.commit()

        parents=[]
        base=datetime(2025,8,1)
        n=100000
        for project,track in PROJECTS:
            for _ in range(25):
                created=base+timedelta(days=random.randint(0,364),hours=random.randint(0,23))
                tid=f"INC{n}"; n+=1
                parent=Ticket(ticket_id=tid,parent_ticket=tid,ticket_type="Parent",project=project,track=track,
                              service=random.choice(SERVICES),part=random.choice(PARTS),priority=random.choice(["P1","P2","P3","P4"]),
                              status=random.choice(["Resolved","Closed","Open"]),created_date=created)
                db.add(parent); parents.append(parent)
        db.commit()

        for p in parents:
            for _ in range(random.choices([0,1,2,3,5,8],[8,18,25,20,12,5])[0]):
                tid=f"INC{n}"; n+=1
                child=Ticket(ticket_id=tid,parent_ticket=p.ticket_id,ticket_type="Child",project=p.project,track=p.track,
                             service=p.service,part=p.part,priority=p.priority,status=random.choice(["Resolved","Closed","Open"]),
                             created_date=p.created_date+timedelta(minutes=random.randint(5,1440)))
                db.add(child)
        db.commit()

        a=500000
        all_tickets=db.query(Ticket).all()
        for t in all_tickets:
            for _ in range(random.choices([0,1,2,3,5],[15,30,30,18,7])[0]):
                aid=f"ALT{a}"; a+=1
                al=Alert(alert_id=aid,alert_time=t.created_date-timedelta(minutes=random.randint(0,240)),
                         project=t.project,track=t.track,service=t.service,part=t.part,
                         alert_type=random.choice(ALERTS),severity=random.choice(["Critical","Major","Minor"]),
                         monitoring_tool="NZG2")
                db.add(al); db.flush()
                db.add(TicketAlert(ticket_id=t.ticket_id,alert_id=aid,relationship="Generated / Correlated"))
        db.commit()
        print("Demo data seeded.")
    finally:
        db.close()

if __name__=="__main__":
    seed()
