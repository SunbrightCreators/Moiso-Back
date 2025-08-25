from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.core.files import File
from django.db import transaction
from django.apps import apps as django_apps

# ─────────── utils ─────────── #

def _load_json(path: str | Path):
    p = Path(path).resolve()
    if not p.exists():
        raise CommandError(f"파일 없음: {p}")
    return json.loads(p.read_text(encoding="utf-8"))

def _ensure_file(path: str | Path, base: Path) -> File:
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

# ─────────── command ─────────── #

class Command(BaseCommand):
    help = "회원가입 → 프로필추가 → 제안글 → 펀딩까지 API 더미데이터 삽입"

    def add_arguments(self, parser):
        parser.add_argument("--users", help="회원가입 JSON")
        parser.add_argument("--profiles", help="프로필 추가 JSON")
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
        FundingImage = None
        try:
            FundingImage = apps.get_model("fundings", "FundingImage")
        except Exception:
            FundingImage = None

        # 회원가입
        if opts.get("users"):
            for row in _load_json(opts["users"]):
                if User.objects.filter(email=row["email"]).exists():
                    continue
                u = User.objects.create_user(
                    email=row["email"],
                    password=row["password"],
                    name=row["name"],
                    birth=row.get("birth"),
                    sex=row.get("sex"),
                    is_marketing_allowed=row.get("is_marketing_allowed", False),
                )
                self.stdout.write(self.style.SUCCESS(f"[User] {u.email} 생성"))

        # 프로필 추가(Proposer)
        if opts.get("profiles"):
            for row in _load_json(opts["profiles"]):
                user = User.objects.get(email=row["email"])
                if not hasattr(user, "proposer"):
                    Proposer.objects.create(
                        user=user,
                        industry=row["industry"],
                        address=row["address"],
                    )
                    self.stdout.write(self.style.SUCCESS(f"[Proposer] {user.email} 프로필 생성"))

        # 제안글
        if opts.get("proposals"):
            for row in _load_json(opts["proposals"]):
                user = User.objects.get(email=row["email"])
                if not hasattr(user, "proposer"):
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

        # 펀딩
        if opts.get("fundings"):
            for row in _load_json(opts["fundings"]):
                founder = User.objects.get(email=row["founder_email"]).founder
                proposal = Proposal.objects.get(id=row["proposal_id"])
                f = Funding.objects.create(
                    proposal=proposal,
                    user=founder,
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

                # 이미지
                for ip in _list(row.get("images")):
                    file = _ensure_file(ip, files_root)
                    if FundingImage:
                        FundingImage.objects.create(funding=f, image=file)
                    elif hasattr(f, "image") and not f.image:
                        f.image.save(file.name, file, save=True)

                # 비디오
                if row.get("video") and hasattr(f, "video"):
                    file = _ensure_file(row["video"], files_root)
                    f.video.save(file.name, file, save=True)

                # 통장 사본
                if row.get("bank_bankbook") and hasattr(f, "bank_bankbook"):
                    file = _ensure_file(row["bank_bankbook"], files_root)
                    f.bank_bankbook.save(file.name, file, save=True)

                # 창업자 사진
                if row.get("founder_image") and hasattr(f, "founder_image"):
                    file = _ensure_file(row["founder_image"], files_root)
                    f.founder_image.save(file.name, file, save=True)

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
            raise CommandError("[DRY-RUN] 롤백 완료")
