from django.conf import settings


class ContentSecurityPolicyReportOnlyMiddleware:
    """Adds a report-only CSP header before the policy is ready to enforce."""

    header_name = "Content-Security-Policy-Report-Only"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        policy = getattr(settings, "CONTENT_SECURITY_POLICY_REPORT_ONLY", None)
        if policy and self.header_name not in response:
            response[self.header_name] = self._serialize_policy(policy)
        return response

    @staticmethod
    def _serialize_policy(policy):
        return "; ".join(
            f"{directive} {' '.join(sources)}" if sources else directive for directive, sources in policy.items()
        )
