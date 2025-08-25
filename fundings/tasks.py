from django.utils import timezone
from django.conf import settings
import logging
import traceback
import sys
import os

# 로거 생성
logger = logging.getLogger("fundings.tasks")

def debug_cron_task():
    """Cron 작업 디버깅용 함수"""
    try:
        now = timezone.now()

        # 기본 시간 정보
        logger.info("=" * 50)
        logger.info("CRON 디버깅 작업 시작")
        logger.info("=" * 50)

        # 상세 시간 정보
        time_info = f"""
        현재 실행 시간: {now.strftime('%Y-%m-%d %H:%M:%S')}
        타임존: {now.tzinfo}
        Unix 타임스탬프: {now.timestamp()}
        요일: {now.strftime('%A')} (숫자: {now.weekday() + 1})
        시간: {now.hour}시 {now.minute}분 {now.second}초
        연도: {now.year}, 월: {now.month}, 일: {now.day}
        이번 주의 몇 번째 날: {now.weekday() + 1}
        이번 해의 몇 번째 날: {now.timetuple().tm_yday}
        """
        logger.info(time_info)

        # 시스템 정보
        system_info = f"""
        Python 버전: {sys.version}
        현재 작업 디렉토리: {os.getcwd()}
        Django 설정: {settings.SETTINGS_MODULE}
        디버그 모드: {settings.DEBUG}
        """
        logger.info("시스템 정보:")
        logger.info(system_info)

        # 환경 변수 정보 (민감하지 않은 것만)
        env_info = f"""
        PATH: {os.environ.get('PATH', 'Not set')[:100]}...
        USER: {os.environ.get('USER', 'Not set')}
        HOME: {os.environ.get('HOME', 'Not set')}
        """
        logger.info("환경 변수 정보:")
        logger.info(env_info)

        logger.info("=" * 50)
        logger.info("CRON 디버깅 작업 완료")
        logger.info("=" * 50)

    except Exception as e:
        logger.error(f"디버깅 작업 중 오류 발생: {str(e)}")
        logger.error(f"오류 상세: {traceback.format_exc()}")


def hourly_task_with_debug():
    """실제 작업 + 디버깅이 포함된 시간별 작업"""
    start_time = timezone.now()

    try:
        logger.info(f"시간별 작업 시작: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # 실제 비즈니스 로직
        # 예: 데이터 정리, 통계 업데이트 등

        # 예시 작업 1: 데이터베이스 정리
        logger.info("데이터베이스 정리 작업 시작")
        # cleanup_old_data()
        logger.info("데이터베이스 정리 완료")

        # 예시 작업 2: 캐시 정리
        logger.info("캐시 정리 작업 시작")
        # clear_expired_cache()
        logger.info("캐시 정리 완료")

        # 작업 완료
        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()

        logger.info(f"시간별 작업 완료: {duration:.2f}초 소요")

    except Exception as e:
        logger.error(f"시간별 작업 실행 중 오류: {str(e)}")
        logger.error(f"오류 상세: {traceback.format_exc()}")

        # 에러 발생 시 알림 (선택사항)
        # send_error_notification(str(e))