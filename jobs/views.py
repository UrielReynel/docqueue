from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .models import Job
from .serializers import JobCreateSerializer, JobSerializer


class JobViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Upload files for processing and check their status.

    Every query is scoped to the calling API key: a key never sees another key's jobs.
    """

    serializer_class = JobSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        qs = Job.objects.filter(api_key=self.request.auth)
        if status_filter := self.request.query_params.get("status"):
            qs = qs.filter(status=status_filter)
        return qs

    def create(self, request):
        serializer = JobCreateSerializer(data=request.data, context={"api_key": request.auth})
        serializer.is_valid(raise_exception=True)
        job = serializer.save()
        return Response(JobSerializer(job).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        job = self.get_object()
        if job.status != Job.Status.FAILED:
            return Response({"detail": "Only failed jobs can be retried."}, status=status.HTTP_409_CONFLICT)
        job.status, job.attempts, job.error = Job.Status.QUEUED, 0, ""
        job.run_after, job.finished_at = timezone.now(), None
        job.save()
        return Response(JobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


@api_view(["GET"])
@authentication_classes([])
@permission_classes([])
def health(request):
    counts = {s: Job.objects.filter(status=s).count() for s in Job.Status.values}
    return Response({"status": "ok", "jobs": counts})
