from rest_framework import serializers

from apps.insight.models import InsightFinding, InsightReport


class InsightReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = InsightReport
        fields = "__all__"


class InsightFindingSerializer(serializers.ModelSerializer):
    class Meta:
        model = InsightFinding
        fields = "__all__"

