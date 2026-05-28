import json
import logging

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger("django.security.csp")


@csrf_exempt
@require_POST
def content_security_policy_report(request):
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except ValueError:
        payload = {"invalid": request.body.decode("utf-8", errors="replace")}

    logger.info("Content Security Policy report received: %s", json.dumps(payload, sort_keys=True))
    return HttpResponse(status=204)
