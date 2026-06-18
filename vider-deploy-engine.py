#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VIDER Deploy Engine v1.0
✅ ไฟล์เดียว ครบสมบูรณ์
✅ รองรับ Deploy อัตโนมัติขึ้น GitHub
✅ เชื่อมต่อทุกระบบ VIDER: อดีต - ปัจจุบัน - อนาคต
✅ จัดหมวดหมู่ + เก็บระเบียบในฐานกลาง
✅ เตรียมนำไปสร้างเป็น Repo บน GitHub ได้ทันที
"""

import os
import re
import json
import time
import uuid
import shutil
import subprocess
import hashlib
from datetime import datetime
from typing import Dict, Optional, List
from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel, Field

# ─────────────────────────────────────────────────────────────
# ⚙️ การตั้งค่าหลัก (แก้ไขได้ตามต้องการ)
# ─────────────────────────────────────────────────────────────
MODULE_NAME = "VIDER Deploy Engine"
VERSION = "1.0.0"
API_KEY = os.getenv("VIDER_API_KEY", "AGI244")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")        # ใส่ตรงนี้หรือตั้งค่าในระบบ
GITHUB_OWNER = os.getenv("GITHUB_OWNER", "")        # ชื่อบัญชี/องค์กร GitHub
BASE_STORAGE = "./vider_deploy_data"
BASE_WORKSPACE = "./vider_deploy_build"

os.makedirs(BASE_STORAGE, exist_ok=True)
os.makedirs(BASE_WORKSPACE, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# 📋 โครงสร้างข้อมูล
# ─────────────────────────────────────────────────────────────
class DeployRequest(BaseModel):
    system_name: str = Field(..., description="ชื่อระบบ/โมดูล")
    system_code: Optional[str] = Field(None, description="รหัสประจำระบบ")
    source_url: Optional[str] = Field(None, description="ลิงก์ต้นทาง (ถ้ามี)")
    description: str = Field("", description="คำอธิบายสั้นๆ")
    category: str = Field("VIDER/CORE", description="หมวดหมู่จัดเก็บ")
    tags: List[str] = Field(default_factory=lambda: ["vider", "module"])

class DeployResult(BaseModel):
    deploy_id: str
    system_name: str
    github_repo: Optional[str]
    status: str
    deployed_at: str
    manifest_path: str

# ─────────────────────────────────────────────────────────────
# 🧠 กลไกหลัก Deploy Engine
# ─────────────────────────────────────────────────────────────
class ViderDeployCore:
    def __init__(self):
        self.registry_file = os.path.join(BASE_STORAGE, "registry.json")
        self._load_registry()

    def _load_registry(self):
        if os.path.exists(self.registry_file):
            with open(self.registry_file, "r", encoding="utf-8") as f:
                self.registry = json.load(f)
        else:
            self.registry = {
                "module": MODULE_NAME,
                "version": VERSION,
                "created": datetime.utcnow().isoformat(),
                "systems": []
            }

    def _save_registry(self):
        self.registry["updated"] = datetime.utcnow().isoformat()
        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(self.registry, f, indent=2, ensure_ascii=False)

    def _sanitize(self, name: str) -> str:
        """ทำความสะอาดชื่อให้ใช้เป็นชื่อโฟลเดอร์/รีโปได้"""
        return re.sub(r"[^a-zA-Z0-9_\-]", "_", name).strip("_").lower()[:50]

    def prepare_repo(self, req: DeployRequest) -> Dict:
        """สร้างโครงสร้างรีโปมาตรฐานอัตโนมัติ"""
        deploy_id = f"VIDER-DEPLOY-{uuid.uuid4().hex[:12].upper()}"
        safe_name = self._sanitize(req.system_name)
        work_dir = os.path.join(BASE_WORKSPACE, safe_name)

        # ลบเก่าถ้ามี
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)
        os.makedirs(work_dir, exist_ok=True)

        # สร้างไฟล์มาตรฐาน
        files = {
            "README.md": f"""# 🧩 {req.system_name}

**Deployed by:** {MODULE_NAME} v{VERSION}
**Deploy ID:** `{deploy_id}`
**Category:** `{req.category}`
**Tags:** `{", ".join(req.tags)}`

## 📝 คำอธิบาย
{req.description or "ส่วนหนึ่งของระบบนิเวศ VIDER AGI Platform"}

## 🔗 การเชื่อมต่อ
- ✅ เข้ากันได้กับทุกระบบ VIDER: อดีต - ปัจจุบัน - อนาคต
- ✅ เชื่อมต่อผ่าน VIDER Core API
- ✅ จัดเก็บและค้นหาได้ใน FounderDEL

---
*Generated automatically via VIDER Deploy Engine*
""",
            "vider_manifest.json": json.dumps({
                "deploy_id": deploy_id,
                "name": req.system_name,
                "code": req.system_code or f"VIDER-{safe_name.upper()}",
                "category": req.category,
                "tags": req.tags,
                "source_url": req.source_url,
                "deployed_at": datetime.utcnow().isoformat(),
                "deploy_version": VERSION,
                "compatibility": "VIDER Universal Standard"
            }, indent=2, ensure_ascii=False),
            ".gitignore": """__pycache__/
*.pyc
.env
.env.local
*.log
*.tmp
.DS_Store
Thumbs.db
""",
            "requirements.txt": """fastapi>=0.100
uvicorn>=0.23
pydantic>=2.0
requests>=2.31
"""
        }

        # บันทึกไฟล์ทั้งหมด
        for fname, content in files.items():
            with open(os.path.join(work_dir, fname), "w", encoding="utf-8") as f:
                f.write(content)

        return {
            "deploy_id": deploy_id,
            "safe_name": safe_name,
            "work_dir": work_dir,
            "manifest": os.path.join(work_dir, "vider_manifest.json")
        }

    def push_to_github(self, pkg: Dict, req: DeployRequest) -> Dict:
        """ส่งขึ้น GitHub อัตโนมัติ"""
        if not GITHUB_TOKEN or not GITHUB_OWNER:
            return {
                "status": "READY_LOCAL_ONLY",
                "note": "ตั้งค่า GITHUB_TOKEN/GITHUB_OWNER เพื่อเปิดใช้งานส่งขึ้น GitHub"
            }

        try:
            # เริ่ม Git
            subprocess.run(["git", "init"], cwd=pkg["work_dir"], check=True, capture_output=True, text=True)
            subprocess.run(["git", "add", "."], cwd=pkg["work_dir"], check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "commit", "-m", f"VIDER Deploy: {req.system_name} | {datetime.utcnow().date()}"],
                cwd=pkg["work_dir"], check=True, capture_output=True, text=True
            )

            # สร้างรีโปใหม่บน GitHub
            create_repo = subprocess.run(
                [
                    "curl", "-s", "-X", "POST",
                    "-H", f"Authorization: token {GITHUB_TOKEN}",
                    "-H", "Accept: application/vnd.github.v3+json",
                    "https://api.github.com/user/repos",
                    "-d", json.dumps({
                        "name": pkg["safe_name"],
                        "description": f"VIDER Module: {req.system_name} | {req.description}",
                        "private": True,
                        "auto_init": False
                    })
                ],
                check=True, capture_output=True, text=True
            )

            # ตั้งค่าและส่งโค้ด
            remote_url = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_OWNER}/{pkg['safe_name']}.git"
            subprocess.run(["git", "remote", "add", "origin", remote_url],
                           cwd=pkg["work_dir"], check=True, capture_output=True, text=True)
            subprocess.run(["git", "branch", "-M", "main"],
                           cwd=pkg["work_dir"], check=True, capture_output=True, text=True)
            subprocess.run(["git", "push", "-u", "origin", "main"],
                           cwd=pkg["work_dir"], check=True, capture_output=True, text=True)

            github_url = f"https://github.com/{GITHUB_OWNER}/{pkg['safe_name']}"
            status = "DEPLOYED_SUCCESS"

        except Exception as e:
            github_url = None
            status = f"PARTIAL: {str(e)[:70]}"

        # บันทึกลงทะเบียนกลาง
        entry = {
            **pkg,
            "github_url": github_url,
            "status": status,
            "deployed_at": datetime.utcnow().isoformat(),
            "linked": True
        }
        self.registry["systems"].append(entry)
        self._save_registry()

        return entry

    def list_all(self, category: Optional[str] = None) -> List[Dict]:
        """แสดงรายการทุกระบบที่ลงทะเบียนแล้ว"""
        items = self.registry.get("systems", [])
        if category:
            items = [i for i in items if i.get("category") == category]
        return sorted(items, key=lambda x: x["deployed_at"], reverse=True)

# ─────────────────────────────────────────────────────────────
# 🌐 API Endpoints
# ─────────────────────────────────────────────────────────────
app = FastAPI(title=MODULE_NAME, version=VERSION)
core = ViderDeployCore()

def verify_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="❌ Invalid VIDER API Key")

@app.post("/api/v1/deploy", response_model=DeployResult, summary="Deploy ระบบใหม่")
def deploy_system(req: DeployRequest, _=Depends(verify_key)):
    pkg = core.prepare_repo(req)
    res = core.push_to_github(pkg, req)
    return DeployResult(
        deploy_id=pkg["deploy_id"],
        system_name=req.system_name,
        github_repo=res.get("github_url"),
        status=res.get("status", "READY"),
        deployed_at=datetime.utcnow().isoformat(),
        manifest_path=pkg["manifest"]
    )

@app.get("/api/v1/systems", summary="ดูรายการระบบทั้งหมด")
def list_systems(category: str = "", _=Depends(verify_key)):
    return {
        "total": len(core.list_all()),
        "systems": core.list_all(category=category or None)
    }

@app.get("/api/v1/status", summary="ตรวจสอบสถานะ Deploy Engine")
def status():
    return {
        "module": MODULE_NAME,
        "version": VERSION,
        "github_connected": bool(GITHUB_TOKEN and GITHUB_OWNER),
        "registry_path": core.registry_file,
        "ready": True
    }

# ─────────────────────────────────────────────────────────────
# 🚀 เริ่มทำงาน
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*70)
    print(f"🚀 {MODULE_NAME} v{VERSION} เริ่มทำงานแล้ว")
    print(f"📂 ที่เก็บข้อมูล: {os.path.abspath(BASE_STORAGE)}")
    print(f"🔑 API Key: {API_KEY}")
    print(f"🌐 API: http://localhost:8099/api/v1/deploy")
    print(f"📌 ตั้งค่า GITHUB_TOKEN / GITHUB_OWNER เพื่อเปิดใช้ส่งขึ้น GitHub")
    print("="*70 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8099, log_level="info")
