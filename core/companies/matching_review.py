"""Review projections shared by preview and locked application in the admin."""

from .models import Product, assess_product_post, normalize_product_post_match_text


def matching_preview(product):
    protected = product.match_status == Product.MatchStatus.CONFIRMED
    post, reason = (product.post, product.match_reason) if protected else assess_product_post(product)
    status = (
        product.match_status
        if protected
        else (
            Product.MatchStatus.AUTO
            if post and normalize_product_post_match_text(product.name) == normalize_product_post_match_text(post.title)
            else Product.MatchStatus.REVIEW
        )
    )
    return {
        "id": product.pk,
        "name": product.name,
        "category_id": product.category_id,
        "old_post_id": product.post_id,
        "old_post": str(product.post) if product.post else "—",
        "old_status": product.match_status,
        "old_reason": product.match_reason,
        "post_id": post.pk if post else None,
        "post": str(post) if post else "—",
        "status": status,
        "status_label": Product.MatchStatus(status).label,
        "reason": reason,
        "protected": protected,
        "changed": not protected
        and (product.post_id, product.match_status, product.match_reason)
        != (post.pk if post else None, status, reason),
    }
