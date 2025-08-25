from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.core.files import File
from django.db import transaction

# ─────────── utils ─────────── #

def _load_json(path: str | Path):
    p = Path(path).resolve()
    if not p.exists():
        raise CommandError(f"파일 없음: {p}")
    return json.loads(p.read_text(encoding="utf-8"))

def _ensure_file(path: str | Path | None, base: Path) -> Optional[File]:
    if not path:
        return None
    p = Path(path)
    if not p.is_absolute():
        p = (base / p).resolve()
    if not p.exists():
        raise CommandError(f"파일 없음: {p}")
    return File(p.open("rb"), name=p.name)

def _list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]

# ─────────── helpers ─────────── #

def _create_proposer_if_absent(user, payload: dict):
    """payload: {"industry": [...], "address": [...]}"""
    Proposer = apps.get_model("accounts", "Proposer")
    if hasattr(user, "proposer") and user.proposer:
        return user.proposer
    return Proposer.objects.create(
        user=user,
        industry=payload.get("industry", []),
        address=payload.get("address", []),
    )

def _create_founder_if_absent(user, payload: dict):
    """payload: {"industry":[...], "address":[...], "target":[...], "business_hours":{...}} 등"""
    Founder = apps.get_model("accounts", "Founder")
    if hasattr(user, "founder") and user.founder:
        return user.founder
    return Founder.objects.create(
        user=user,
        industry=payload.get("industry", []),
        address=payload.get("address", []),
        target=payload.get("target", []),
        business_hours=payload.get("business_hours", None),
    )

# ─────────── command ─────────── #

class Command(BaseCommand):
    help = "회원가입 → 프로필추가 → 제안글 → 펀딩까지 API 더미데이터 삽입"

    def add_arguments(self, parser):
        parser.add_argument("--users", help="회원가입 JSON")
        parser.add_argument("--profiles", help="프로필 추가 JSON (proposer/founder 혼합 가능)")
        parser.add_argument("--proposals", help="제안글 추가 JSON")
        parser.add_argument("--fundings", help="펀딩 추가 JSON")
        parser.add_argument("--files-root", default=".", help="첨부파일 root 폴더")
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **opts):
        files_root = Path(opts["files_root"]).resolve()

        User = get_user_model()
        Proposer = apps.get_model("accounts", "Proposer")
        Founder = apps.get_model("accounts", "Founder")
        Proposal = apps.get_model("proposals", "Proposal")
        Funding = apps.get_model("fundings", "Funding")
        Reward = apps.get_model("fundings", "Reward")
        try:
            FundingImage = apps.get_model("fundings", "FundingImage")
        except Exception:
            FundingImage = None

        # 1) 회원가입 (+ 즉시 프로필 생성 지원)
        if opts.get("users"):
            for row in _load_json(opts["users"]):
                email = row["email"]
                if User.objects.filter(email=email).exists():
                    self.stdout.write(self.style.WARNING(f"[User] {email} 이미 존재 — 건너뜀"))
                    user = User.objects.get(email=email)
                else:
                    user = User.objects.create_user(
                        email=email,
                        password=row["password"],
                        name=row["name"],
                        birth=row.get("birth"),
                        sex=row.get("sex"),
                        is_marketing_allowed=row.get("is_marketing_allowed", False),
                    )
                    self.stdout.write(self.style.SUCCESS(f"[User] {user.email} 생성"))

                # users.json 안에 즉시 프로필 생성 요청이 있으면 처리
                if "proposer_profile" in row and row["proposer_profile"]:
                    _create_proposer_if_absent(user, row["proposer_profile"])
                    self.stdout.write(self.style.SUCCESS(f"[Proposer] {user.email} 프로필 생성/유지"))

                if "founder_profile" in row and row["founder_profile"]:
                    _create_founder_if_absent(user, row["founder_profile"])
                    self.stdout.write(self.style.SUCCESS(f"[Founder] {user.email} 프로필 생성/유지"))

        # 2) 프로필 추가 (proposer / founder 모두 지원)
        #    예: {"email": "...", "role": "proposer"|"founder", ...프로필필드...}
        if opts.get("profiles"):
            for row in _load_json(opts["profiles"]):
                user = User.objects.get(email=row["email"])
                role = (row.get("role") or row.get("type") or "proposer").lower()
                payload = {k: v for k, v in row.items() if k not in ("email", "role", "type")}

                if role == "proposer":
                    _create_proposer_if_absent(user, payload)
                    self.stdout.write(self.style.SUCCESS(f"[Proposer] {user.email} 프로필 생성/유지"))
                elif role == "founder":
                    _create_founder_if_absent(user, payload)
                    self.stdout.write(self.style.SUCCESS(f"[Founder] {user.email} 프로필 생성/유지"))
                else:
                    raise CommandError(f"[profiles] role/type 값이 올바르지 않음: {role}")

        # 3) 제안글
        if opts.get("proposals"):
            for row in _load_json(opts["proposals"]):
                user = User.objects.get(email=row["email"])
                if not hasattr(user, "proposer") or user.proposer is None:
                    raise CommandError(f"{user.email} 은 proposer 프로필이 없음")

                p = Proposal.objects.create(
                    user=user.proposer,
                    title=row["title"],
                    content=row["content"],
                    industry=row["industry"],
                    business_hours=row["business_hours"],
                    address=row["address"],
                    position=row["position"],
                    radius=row["radius"],
                )
                self.stdout.write(self.style.SUCCESS(f"[Proposal] {p.id} {p.title} 생성"))
                # (필요하면 Proposal 이미지/파일 처리 로직을 여기에 추가)

        # 4) 펀딩
        if opts.get("fundings"):
            for row in _load_json(opts["fundings"]):
                founder_email = row["founder_email"]
                try:
                    founder_user = User.objects.get(email=founder_email)
                except User.DoesNotExist:
                    raise CommandError(f"[Funding] founder user 없음: {founder_email}")

                if not hasattr(founder_user, "founder") or founder_user.founder is None:
                    raise CommandError(f"[Funding] founder 프로필 없음: {founder_email}")

                try:
                    proposal = Proposal.objects.get(id=row["proposal_id"])
                except Proposal.DoesNotExist:
                    raise CommandError(f"[Funding] proposal_id={row['proposal_id']} 없음")

                f = Funding.objects.create(
                    proposal=proposal,
                    user=founder_user.founder,
                    business_name=row["business_name"],
                    title=row["title"],
                    summary=row["summary"],
                    content=row["content"],
                    business_hours=row["business_hours"],
                    radius=row["radius"],
                    contact=row["contact"],
                    goal_amount=row["goal_amount"],
                    schedule=row["schedule"],
                    schedule_description=row["schedule_description"],
                    expected_opening_date=row["expected_opening_date"],
                    amount_description=row["amount_description"],
                    founder_name=row["founder_name"],
                    founder_description=row["founder_description"],
                    bank_category=row["bank_category"],
                    bank_account=row["bank_account"],
                    policy=row["policy"],
                    expected_problem=row["expected_problem"],
                    status=row["status"],
                )

                # 이미지(복수/단수 키 모두 허용)
                image_list = _list(row.get("images") or row.get("image"))
                for ip in image_list:
                    file = _ensure_file(ip, files_root)
                    if not file:
                        continue
                    if FundingImage:
                        FundingImage.objects.create(funding=f, image=file)
                    elif hasattr(f, "image") and not f.image:
                        f.image.save(file.name, file, save=True)

                # 비디오
                vfile = _ensure_file(row.get("video"), files_root)
                if vfile and hasattr(f, "video"):
                    f.video.save(vfile.name, vfile, save=True)

                # 통장 사본
                bfile = _ensure_file(row.get("bank_bankbook"), files_root)
                if bfile and hasattr(f, "bank_bankbook"):
                    f.bank_bankbook.save(bfile.name, bfile, save=True)

                # 창업자 사진
                pfile = _ensure_file(row.get("founder_image"), files_root)
                if pfile and hasattr(f, "founder_image"):
                    f.founder_image.save(pfile.name, pfile, save=True)

                # 리워드
                for r in _list(row.get("reward")):
                    Reward.objects.create(
                        funding=f,
                        category=r["category"],
                        title=r["title"],
                        content=r["content"],
                        amount=r["amount"],
                    )

                self.stdout.write(self.style.SUCCESS(f"[Funding] {f.id} {f.title} 생성"))

        if opts["dry_run"]:
            # 전체 롤백
            raise CommandError("[DRY-RUN] 롤백 완료")
