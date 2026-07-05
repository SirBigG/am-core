import time
import traceback
from tempfile import NamedTemporaryFile

from django.db import transaction
from django.utils import timezone

from core.registry.models import RegistryImportJob
from core.registry.parser import import_registry_workbook


def claim_next_registry_import_job():
    with transaction.atomic():
        jobs = list(
            RegistryImportJob.objects.select_for_update()
            .filter(status__in=[RegistryImportJob.Status.PENDING, RegistryImportJob.Status.RUNNING])
            .order_by("created_at")
        )
        if any(job.status == RegistryImportJob.Status.RUNNING for job in jobs):
            return None
        job = next((job for job in jobs if job.status == RegistryImportJob.Status.PENDING), None)
        if job is None:
            return None
        mark_registry_import_job_running(job)
        return job


def mark_registry_import_job_running(job):
    job.status = RegistryImportJob.Status.RUNNING
    job.started_at = timezone.now()
    job.finished_at = None
    job.error = ""
    job.save(update_fields=["status", "started_at", "finished_at", "error"])


def process_registry_import_job(job):
    try:
        with job.source_file.open("rb") as source_file:
            suffix = "." + job.original_filename.rsplit(".", 1)[-1].lower()
            with NamedTemporaryFile(suffix=suffix) as temporary_file:
                for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
                    temporary_file.write(chunk)
                temporary_file.flush()
                summary = import_registry_workbook(temporary_file.name)
    except Exception:
        job.status = RegistryImportJob.Status.FAILED
        job.error = traceback.format_exc()
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error", "finished_at"])
        return False

    job.status = RegistryImportJob.Status.SUCCEEDED
    job.summary = summary
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "summary", "finished_at"])
    return True


def process_registry_import_jobs(*, limit=1, poll=False, sleep_seconds=10, stdout=None, stderr=None, style=None):
    processed = 0
    while True:
        job = claim_next_registry_import_job()
        if job is None:
            if stdout:
                stdout.write("No pending registry import jobs.")
            if not poll:
                return processed
            if limit is not None and processed >= limit:
                return processed
            time.sleep(sleep_seconds)
            continue

        if stdout:
            stdout.write(f"Processing registry import job #{job.id}: {job.original_filename}")
        succeeded = process_registry_import_job(job)
        processed += 1
        if stdout and succeeded:
            message = f"Registry import job #{job.id} succeeded."
            stdout.write(style.SUCCESS(message) if style else message)
        if stderr and not succeeded:
            message = f"Registry import job #{job.id} failed."
            stderr.write(style.ERROR(message) if style else message)
        if limit is not None and processed >= limit:
            return processed
