from django import template

from products.highlighting import highlight_matches


register = template.Library()

register.filter('highlight_query', highlight_matches)
