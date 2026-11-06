from django.conf import settings
from rest_framework import serializers

from .models import Job, next_nightly_run
from .processors import UnsupportedFile, detect_kind


class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = [
            "id",
            "original_name",
            "kind",
            "mode",
            "status",
            "run_after",
            "attempts",
            "result",
            "error",
            "created_at",
            "started_at",
            "finished_at",
        ]
        read_only_fields = fields


class JobCreateSerializer(serializers.Serializer):
    file = serializers.FileField()
    mode = serializers.ChoiceField(choices=Job.Mode.choices, default=Job.Mode.NOW)

    def validate_file(self, upload):
        max_bytes = settings.DOCQUEUE_MAX_UPLOAD_MB * 1024 * 1024
        if upload.size > max_bytes:
            raise serializers.ValidationError(f"File is larger than {settings.DOCQUEUE_MAX_UPLOAD_MB} MB.")
        head = upload.read(16)
        upload.seek(0)
        try:
            self.context["kind"] = detect_kind(upload.name, head)
        except UnsupportedFile as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return upload

    def create(self, validated_data):
        mode = validated_data["mode"]
        job = Job(
            api_key=self.context["api_key"],
            original_name=validated_data["file"].name,
            kind=self.context["kind"],
            mode=mode,
        )
        if mode == Job.Mode.NIGHTLY:
            job.run_after = next_nightly_run()
        # Save the file under the job's own UUID folder.
        job.file.save(validated_data["file"].name, validated_data["file"], save=False)
        job.save()
        return job
