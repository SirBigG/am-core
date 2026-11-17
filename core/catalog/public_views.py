from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from core.classifier.models import Category
from core.posts.models import Post

from .public_blocks import public_blocks


@never_cache
@require_safe
def related_catalog(request, anchor_type, pk):
    if anchor_type not in {"category", "post"}:
        return JsonResponse({"error": "unknown_anchor"}, status=404)
    category = anchor_type == "category"
    model = Category if category else Post
    anchor = model.objects.only("pk", "entity_id", "absolute_url").filter(pk=pk).first()
    data = {"version": 1, "blocks": [], "crop_choices": []}
    if anchor:
        result = public_blocks(
            anchor, anchor.absolute_url, request.GET, category=category, strict=True, include_offers=True
        )
        data.update(blocks=result["blocks"], crop_choices=result["crop_choices"])
        if result["error"]:
            data["error"] = result["error"]
    response = JsonResponse(data, status=400 if "error" in data else 200)
    response["X-Robots-Tag"] = "noindex, follow"
    return response
