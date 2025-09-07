import csv, io, re
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, Response
from bson import ObjectId
from database import get_db, ALLOWED_STATUSES
from auth_helpers import teacher_required
from . import teacher_bp

# -------- Utilities --------
def clean_phone(s: str | None) -> str:
    s = (s or "").strip()
    # keep digits and common dialing symbols
    return re.sub(r"[^\d+()\-\s]", "", s)

# -------- Views --------
@teacher_bp.get("/students")
@teacher_required
def students_list():
    db = get_db()
    q = (request.args.get("q") or "").strip()
    filt = {}
    if q:
        filt = {"$or": [
            {"first_name": {"$regex": q, "$options": "i"}},
            {"last_name": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
            {"student_id": {"$regex": q, "$options": "i"}},
            {"classes": {"$elemMatch": {"$regex": q, "$options": "i"}}},
            {"dad_name": {"$regex": q, "$options": "i"}},
            {"mom_name": {"$regex": q, "$options": "i"}},
            {"dad_phone": {"$regex": q, "$options": "i"}},
            {"mom_phone": {"$regex": q, "$options": "i"}},
        ]}
    docs = list(db.students.find(filt).sort([("last_name", 1), ("first_name", 1)]))
    return render_template("teacher/students_list.html",
                           students=docs,
                           q=q,
                           ALLOWED_STATUSES=sorted(ALLOWED_STATUSES))

@teacher_bp.post("/students")
@teacher_required
def students_create_or_update():
    db = get_db()
    d = request.form
    student_id = (d.get("student_id") or "").strip() or None
    email = (d.get("email") or "").strip().lower() or None
    status = (d.get("reg_status") or "pending").strip().lower()

    if status not in ALLOWED_STATUSES:
        flash("Invalid status.", "danger")
        return redirect(url_for("teacher.students_list"))

    doc = {
        "first_name": (d.get("first_name") or "").strip(),
        "last_name": (d.get("last_name") or "").strip(),
        "email": email,
        "student_id": student_id,
        "grade": int(d.get("grade")) if (d.get("grade") or "").strip().isdigit() else None,
        "classes": [c.strip() for c in (d.get("classes") or "").split("|") if c.strip()],
        "reg_status": status,
        "notes": (d.get("notes") or "").strip(),
        # NEW parent fields
        "dad_name": (d.get("dad_name") or "").strip(),
        "dad_phone": clean_phone(d.get("dad_phone")),
        "mom_name": (d.get("mom_name") or "").strip(),
        "mom_phone": clean_phone(d.get("mom_phone")),
        "updated_at": datetime.utcnow(),
    }

    key = {"student_id": student_id} if student_id else {"email": email}
    if not key.get("student_id") and not key.get("email"):
        flash("Need student_id or email.", "danger")
        return redirect(url_for("teacher.students_list"))

    existing = db.students.find_one(key)
    if existing:
        db.students.update_one({"_id": existing["_id"]}, {"$set": doc})
        flash("Student updated.", "success")
    else:
        doc["created_at"] = datetime.utcnow()
        db.students.insert_one(doc)
        flash("Student created.", "success")
    return redirect(url_for("teacher.students_list"))

@teacher_bp.post("/students/status/<id>")
@teacher_required
def students_update_status(id):
    db = get_db()
    status = (request.form.get("reg_status") or "").strip().lower()
    if status not in ALLOWED_STATUSES:
        flash("Invalid status.", "danger")
        return redirect(url_for("teacher.students_list"))

    db.students.update_one({"_id": ObjectId(id)}, {"$set": {
        "reg_status": status,
        "updated_at": datetime.utcnow()
    }})
    flash("Status updated.", "success")
    return redirect(url_for("teacher.students_list"))

@teacher_bp.get("/students/template.csv")
@teacher_required
def students_template():
    headers = [
        "student_id","first_name","last_name","email","grade","classes",
        "reg_status","notes",
        "dad_name","dad_phone","mom_name","mom_phone"   # parent fields
    ]
    return Response(",".join(headers) + "\n",
                    mimetype="text/csv",
                    headers={"Content-Disposition":"attachment; filename=students_template.csv"})

@teacher_bp.post("/students/upload")
@teacher_required
def students_upload():
    db = get_db()   
    """
    CSV columns (header must match):
    student_id,first_name,last_name,email,grade,classes,reg_status,notes,dad_name,dad_phone,mom_name,mom_phone
    - classes: pipe-separated (Algebra 1 - Fall 2025|AMC 8)
    - reg_status: pending|registered|waitlisted|dropped
    """
    f = request.files.get("file")
    if not f:
        flash("No file uploaded.", "danger")
        return redirect(url_for("teacher.students_list"))

    text = io.TextIOWrapper(f.stream, encoding="utf-8", errors="ignore")
    reader = csv.DictReader(text)
    created = updated = errors = 0
    error_rows = []

    for i, row in enumerate(reader, start=2):  # i=2 because header is line 1
        try:
            student_id = (row.get("student_id") or "").strip() or None
            email = (row.get("email") or "").strip().lower() or None
            status = (row.get("reg_status") or "pending").strip().lower()
            if status not in ALLOWED_STATUSES:
                raise ValueError(f"Invalid reg_status '{status}'")

            doc = {
                "first_name": (row.get("first_name") or "").strip(),
                "last_name": (row.get("last_name") or "").strip(),
                "email": email,
                "student_id": student_id,
                "grade": int(row.get("grade")) if (row.get("grade") or "").strip().isdigit() else None,
                "classes": [c.strip() for c in (row.get("classes") or "").split("|") if c.strip()],
                "reg_status": status,
                "notes": (row.get("notes") or "").strip(),
                # parent fields
                "dad_name": (row.get("dad_name") or "").strip(),
                "dad_phone": clean_phone(row.get("dad_phone")),
                "mom_name": (row.get("mom_name") or "").strip(),
                "mom_phone": clean_phone(row.get("mom_phone")),
                "updated_at": datetime.utcnow(),
            }

            key = {"student_id": student_id} if student_id else {"email": email}
            if not key.get("student_id") and not key.get("email"):
                raise ValueError("Missing both student_id and email.")

            ex = db.students.find_one(key)
            if ex:
                db.students.update_one({"_id": ex["_id"]}, {"$set": doc})
                updated += 1
            else:
                doc["created_at"] = datetime.utcnow()
                db.students.insert_one(doc)
                created += 1

        except Exception as e:
            errors += 1
            row["_error"] = f"Row {i}: {e}"
            error_rows.append(row)

    if errors:
        out = io.StringIO()
        w = csv.DictWriter(out, fieldnames=list(error_rows[0].keys()))
        w.writeheader()
        w.writerows(error_rows)
        out.seek(0)
        return Response(out.read(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=upload_errors.csv"})

    flash(f"Upload done. Created: {created}, Updated: {updated}.", "success")
    return redirect(url_for("teacher.students_list"))

@teacher_bp.get("/students/export.csv")
@teacher_required
def students_export():
    db = get_db()
    docs = list(db.students.find().sort([("last_name", 1), ("first_name", 1)]))
    out = io.StringIO()
    headers = [
        "student_id","first_name","last_name","email","grade","classes",
        "reg_status","notes",
        "dad_name","dad_phone","mom_name","mom_phone",
        "updated_at","created_at"
    ]
    w = csv.DictWriter(out, fieldnames=headers)
    w.writeheader()
    for d in docs:
        w.writerow({
            "student_id": d.get("student_id",""),
            "first_name": d.get("first_name",""),
            "last_name": d.get("last_name",""),
            "email": d.get("email",""),
            "grade": d.get("grade",""),
            "classes": "|".join(d.get("classes",[]) or []),
            "reg_status": d.get("reg_status",""),
            "notes": d.get("notes",""),
            "dad_name": d.get("dad_name",""),
            "dad_phone": d.get("dad_phone",""),
            "mom_name": d.get("mom_name",""),
            "mom_phone": d.get("mom_phone",""),
            "updated_at": d.get("updated_at",""),
            "created_at": d.get("created_at",""),
        })
    out.seek(0)
    return Response(out.read(), mimetype="text/csv",
                    headers={"Content-Disposition":"attachment; filename=students_export.csv"})
