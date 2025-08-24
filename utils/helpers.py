#제안자의 is_address 계산
def resolve_viewer_addr(user, profile: str) -> dict | list:
    profile = (profile or "").lower()
    keys = ("sido", "sigungu", "eupmyundong")

    # Founder: ArrayField(JSON[]) 그대로 사용
    if profile == "founder" and getattr(user, "founder", None):
        addrs = getattr(user.founder, "address", None)
        return addrs or []

    # Proposer: 최신 ProposerLevel.address 사용
    if profile == "proposer" and getattr(user, "proposer", None):
        from accounts.models import ProposerLevel
        addr = (
            ProposerLevel.objects
            .filter(user=user.proposer)
            .order_by("-id")
            .values_list("address", flat=True)
            .first()
        ) or {}
        # 키 3개만 추려서 반환(없으면 빈 dict)
        if isinstance(addr, dict) and all(k in addr for k in keys):
            return {k: addr.get(k) for k in keys}
        return {}

    return {}