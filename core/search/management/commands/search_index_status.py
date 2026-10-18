import json

from django.core.management.base import BaseCommand
from django.db.models import Count

from core.search.models import SearchDirtyScope, SearchDocument, SearchIndexState


class Command(BaseCommand):
    help = "Show active search generation, document counts and pending resource revisions."

    def handle(self, *args, **options):
        state = SearchIndexState.objects.filter(pk=1).first()
        counts = (
            dict(
                SearchDocument.objects.filter(generation=state.active_generation)
                .values("resource_type")
                .annotate(total=Count("pk"))
                .values_list("resource_type", "total")
            )
            if state and state.active_generation
            else {}
        )
        self.stdout.write(
            json.dumps(
                {
                    "ready": bool(state and state.active_generation),
                    "generation": str(state.active_generation) if state else None,
                    "updated_at": state.updated_at.isoformat() if state else None,
                    "documents": counts,
                    "pending": dict(
                        SearchDirtyScope.objects.values("resource_type")
                        .annotate(total=Count("pk"))
                        .values_list("resource_type", "total")
                    ),
                },
                ensure_ascii=False,
            )
        )
