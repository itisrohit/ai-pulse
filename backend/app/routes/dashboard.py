from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from ..auth import current_membership

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Client request: never show a team with fewer respondents than this, so no one can be identified
MIN_GROUP_SIZE = 5


def level_for(avg):
    if avg is None:
        return "Not assessed"
    if avg < 1.5:
        return "Beginner"
    if avg < 2.5:
        return "Exploring"
    if avg < 3.5:
        return "Practitioner"
    return "Leader"


@router.get("")
def org_dashboard(m: models.Membership = Depends(current_membership), db: Session = Depends(get_db)):
    if m.role != "admin":
        raise HTTPException(403, "Admins only")

    # Use the org from the token, never one sent by the client
    org = db.get(models.Organization, m.org_id)
    members = db.query(models.Membership).filter_by(org_id=m.org_id).all()
    departments = []
    hidden = []
    all_flags = {}
    for dept in org.departments:
        dept_members = [x for x in members if x.department_id == dept.id]
        scores = []
        dept_flags = []
        responded = 0
        for dm in dept_members:
            rows = db.query(models.Response).filter_by(membership_id=dm.id).all()
            if rows:
                responded += 1
            for r in rows:
                if r.score is not None:
                    scores.append(r.score)
                dept_flags += r.flags or []
        # Too few people to stay anonymous: hide this team's scores and risks
        if responded < MIN_GROUP_SIZE:
            hidden.append(dept.name)
            continue
        for f in dept_flags:
            all_flags[f] = all_flags.get(f, 0) + 1
        avg = sum(scores) / len(scores) if scores else None
        departments.append({
            "department": dept.name,
            "employees": len(dept_members),
            "responded": responded,
            "average_score": round(avg, 2) if avg is not None else None,
            "level": level_for(avg),
        })

    return {
        "organization": org.name,
        "departments": departments,
        "hidden_departments": hidden,
        "top_risks": sorted(all_flags.items(), key=lambda kv: -kv[1])[:5],
    }
