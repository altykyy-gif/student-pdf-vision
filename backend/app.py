import base64
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import requests
from flask import Flask, jsonify, request, send_from_directory

ROOT = Path(__file__).resolve().parent
MODEL = os.getenv("VISION_MODEL", "gemini-3.1-pro-preview")
API_BASE = os.getenv("OPENAI_API_BASE", "").rstrip("/")
API_KEY = os.getenv("OPENAI_API_KEY", "")
app = Flask(__name__, static_folder=str(ROOT))

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = os.getenv("FRONTEND_ORIGIN", "*")
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

SCHEMA = {
    "type": "object",
    "properties": {
        "records": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "grade": {"type": "string"},
                    "year": {"type": "string"},
                    "gender": {"type": "string", "enum": ["M", "F"]},
                    "date": {"type": "string"},
                    "registration_number": {"type": "string"},
                },
                "required": ["name", "grade", "year", "gender", "date", "registration_number"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["records"],
    "additionalProperties": False,
}

SYSTEM = """أنت نظام قراءة مستندات عربي بصري عالي الدقة. اقرأ الجدول من الصورة كما يظهر بصريًا، ولا تعتمد على طبقة النص المشوهة داخل PDF. هذه صفحة من قائمة طلبة ليبية. استخرج كل صف طالب ظاهر في الصفحة فقط، ولا تسقط أي صف ولا تخترع أي صف. احفظ الأسماء حرفيًا كما تراها، خصوصًا الألف واللام في: إيلاف، حلا، عبدالله، عبدالسلام. لا تطبق تصحيحًا لغويًا تخمينيًا. أعد JSON مطابقًا للمخطط فقط."""


def pdf_pages(path: Path, out: Path):
    info = subprocess.check_output(["pdfinfo", str(path)], text=True, stderr=subprocess.STDOUT)
    pages = int(re.search(r"^Pages:\s+(\d+)", info, re.M).group(1))
    subprocess.run(["pdftoppm", "-png", "-r", "240", "-f", "1", "-l", str(pages), str(path), str(out / "page")], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return sorted(out.glob("page-*.png"), key=lambda p: int(re.search(r"-(\d+)\.png$", p.name).group(1)))


def ask_model(image_path: Path, page_no: int):
    if not API_KEY or not API_BASE:
        raise RuntimeError("لم يتم ضبط اتصال نموذج الرؤية في الخادم")
    image = base64.b64encode(image_path.read_bytes()).decode("ascii")
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": [
                {"type": "text", "text": f"اقرأ الصفحة رقم {page_no}. استخرج جميع صفوف الطلبة الظاهرة، بما فيها الصف والعام والجنس لكل صف."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image}", "detail": "high"}},
            ]},
        ],
        "max_tokens": 12000,
        "response_format": {"type": "json_schema", "json_schema": {"name": "student_page", "strict": True, "schema": SCHEMA}},
    }
    r = requests.post(f"{API_BASE}/chat/completions", headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}, json=payload, timeout=240)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    return json.loads(content)["records"]


def validate(records):
    clean = []
    for r in records:
        name = str(r.get("name", "")).strip()
        if not name or len(name) < 2:
            raise ValueError("وجد سجلًا بلا اسم كامل")
        gender = r.get("gender")
        if gender not in ("M", "F"):
            raise ValueError("وجد سجلًا بجنس غير معروف")
        grade = str(r.get("grade", "")).strip()
        grade_match = re.search(r"(الأول|الاول|الثاني|الثانى|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع)\s*(ثانوي|أساسي|اساسي)?", grade)
        if grade_match:
            first = {"الاول": "الأول", "الثانى": "الثاني"}.get(grade_match.group(1), grade_match.group(1))
            grade = f"{first}{(' ' + grade_match.group(2)) if grade_match.group(2) else ''}"
        year = str(r.get("year", "")).strip()
        years = re.findall(r"20\d{2}", year)
        if len(years) >= 2:
            ordered = sorted({int(years[0]), int(years[1])}, reverse=True)
            year = f"{ordered[0]} / {ordered[1]}"
        clean.append({
            "name": name,
            "grade": grade,
            "year": year,
            "gender": gender,
            "date": str(r.get("date", "")).strip(),
            "registration_number": str(r.get("registration_number", "")).strip(),
        })
    if not clean:
        raise ValueError("لم يتم العثور على أي سجل طالب صالح في ملف PDF")
    return clean


@app.get("/")
def index():
    return send_from_directory(ROOT, "index.html")


@app.post("/api/extract")
def extract():
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename.lower().endswith(".pdf"):
        return jsonify({"error": "الرجاء رفع ملف PDF"}), 400
    with tempfile.TemporaryDirectory(prefix="student-pdf-") as td:
        work = Path(td); pdf = work / "input.pdf"; uploaded.save(pdf)
        try:
            pages = pdf_pages(pdf, work)
            records = []
            for i, image in enumerate(pages, 1):
                records.extend(ask_model(image, i))
            records = validate(records)
            return jsonify({"ok": True, "model": MODEL, "count": len(records), "students": records})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 422

@app.route("/api/extract", methods=["OPTIONS"])
def extract_options():
    return ("", 204)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=False)
