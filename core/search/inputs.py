"""Search input bounds shared by indexed search and the schema-independent
fallback."""

MAX_QUERY_LENGTH = 255


def clean_query(value):
    return " ".join(value.split())[:MAX_QUERY_LENGTH]
