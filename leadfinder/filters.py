def is_startup(lead, keywords) -> bool:
    hay = " ".join([p for p in [lead.name, lead.category, lead.website] if p]).lower()
    for kw in keywords or []:
        if kw.lower() in hay:
            return True
    return False


def _website_policy(filt: dict) -> str:
    policy = filt.get("website_policy")
    if policy:
        return str(policy).lower()
    if "require_missing_website" in filt:
        return "only_missing" if filt.get("require_missing_website") else "allow_all"
    return "allow_all"


def passes_filters(lead, cfg: dict) -> bool:
    filt = cfg.get("filters", {})
    if filt.get("exclude_startups"):
        if is_startup(lead, filt.get("startup_keywords", [])):
            return False

    policy = _website_policy(filt)
    if policy == "exclude_missing":
        if not lead.website:
            return False
    if policy == "only_missing":
        if lead.website:
            return False
    return True
