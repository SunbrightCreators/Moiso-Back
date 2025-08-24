from django.core.management.base import BaseCommand
from accounts.services import ProposerLevelingService

class Command(BaseCommand):
    help = "주간 활동을 기반으로 Proposer 레벨을 재계산합니다."

    def handle(self, *args, **options):
        svc = ProposerLevelingService()
        svc.run_for_all()
        self.stdout.write(self.style.SUCCESS("Done: proposer levels recalculated."))