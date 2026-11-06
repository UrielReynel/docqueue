from django.contrib import admin

from .models import APIKey, Job


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "prefix", "created_at", "last_used_at", "revoked")
    readonly_fields = ("prefix", "hashed_key", "created_at", "last_used_at")


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("original_name", "kind", "mode", "status", "attempts", "created_at")
    list_filter = ("status", "kind", "mode")
    readonly_fields = [f.name for f in Job._meta.fields]
