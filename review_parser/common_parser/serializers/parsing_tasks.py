from rest_framework import serializers


class ParsingTaskStartSerializer(serializers.Serializer):
    task_id = serializers.CharField()
    branch_provider_id = serializers.IntegerField()
    status = serializers.CharField()


class ParsingTaskStatusSerializer(serializers.Serializer):
    task_id = serializers.CharField()
    status = serializers.CharField()
    result = serializers.JSONField(allow_null=True, required=False)
