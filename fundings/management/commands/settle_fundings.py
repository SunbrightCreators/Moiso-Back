from django.core.management.base import BaseCommand
from fundings.services import FundingSettlementService

class Command(BaseCommand):
    help = "마감된(IN_PROGRESS) 펀딩을 성공/실패로 정산합니다."

    def handle(self, *args, **options):
        svc = FundingSettlementService()
        result = svc.run()
        self.stdout.write(
            self.style.SUCCESS(
                f"settled: {result.updated} (succeeded={result.succeeded}, failed={result.failed}, skipped={result.skipped})"
            )
        )