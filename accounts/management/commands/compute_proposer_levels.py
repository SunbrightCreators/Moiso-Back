from __future__ import annotations
from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone
from datetime import datetime
from accounts.services import ProposerWeeklyLevelComputer

class Command(BaseCommand):
    help = "최근 7일(or 주어진 윈도우) 기준으로 Proposer 지역 레벨을 산정/업데이트합니다."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--start", type=str, default=None,
                            help="윈도우 시작 (ISO: 2025-08-18T00:00:00+09:00). 미지정 시 끝-7일")
        parser.add_argument("--end", type=str, default=None,
                            help="윈도우 끝   (ISO: 2025-08-25T00:00:00+09:00). 미지정 시 now()")
        parser.add_argument("--ids", nargs="*", default=None,
                            help="특정 proposer id(nanoid)들만 처리 (공백 구분 다수)")

    def handle(self, *args, **options):
        start_raw = options.get("start")
        end_raw = options.get("end")
        ids = options.get("ids")

        def _parse_iso(s: str):
            try:
                # Python 3.11+: fromisoformat가 TZ를 해석
                dt = datetime.fromisoformat(s)
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt, timezone.get_current_timezone())
                return dt
            except Exception:
                self.stderr.write(self.style.WARNING(f"Invalid datetime ISO format: {s}"))
                return None

        start = _parse_iso(start_raw) if start_raw else None
        end = _parse_iso(end_raw) if end_raw else None

        comp = ProposerWeeklyLevelComputer(window_start=start, window_end=end)
        res = comp.run(only_proposer_ids=ids)

        total_rows = sum(res.values())
        total_users = len(res)
        self.stdout.write(self.style.SUCCESS(
            f"[compute_proposer_levels] users={total_users}, updated_rows={total_rows}"
        ))
