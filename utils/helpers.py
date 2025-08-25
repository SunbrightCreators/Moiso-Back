#제안자의 is_address 계산
def resolve_viewer_addr(user, profile: str) -> dict | list:
    profile = (profile or "").lower()
    keys = ("sido", "sigungu", "eupmyundong")

    # Founder: ArrayField(JSON[]) 그대로 사용
    if profile == "founder" and getattr(user, "founder", None):
        addrs = getattr(user.founder, "address", None)
        return addrs or []

    # Proposer: 보유한 모든 ProposerLevel.address 사용  ← (수정 후)
    if profile == "proposer" and getattr(user, "proposer", None):
        from accounts.models import ProposerLevel
        # 사용자가 가진 모든 레벨 주소를 가져와서, 시/군구/읍면동만 추린 리스트로 반환
        addr_rows = list(
            ProposerLevel.objects
            .filter(user=user.proposer)
            .order_by("-id")
            .values_list("address", flat=True)
        )
        result = []
        for addr in addr_rows:
            if isinstance(addr, dict) and all(k in addr for k in keys):
                result.append({k: addr.get(k) for k in keys})
        # 하나도 유효한 게 없으면 빈 dict 대신 빈 리스트 반환(호출부가 list/dict 모두 처리)
        return result

    return {}