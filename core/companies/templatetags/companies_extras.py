from django import template

from core.companies.models import Product

register = template.Library()


# inclusion tag to display products for a post by post_id
@register.inclusion_tag("companies/products_for_post.html")
def products_for_post(post_id):
    products = Product.objects.select_related("company").filter(post_id=post_id)
    return {"products": products}
