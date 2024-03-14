from rest_framework import serializers

from .models import Tag, Typetag, ReplayBasic, ManualTagger # , GameSession

class ReplayBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReplayBasic
        fields = ("replay", "game", "user", "url", "level")

class TagSerializer(serializers.ModelSerializer):
    # session = Session.objects.get(pk=session)
    class Meta:
        model = Tag
        fields = ["replay", "competence", "typeTag", "tag", "annotationTime", "finalAnnotationTime"]
        depth = 3

        
class ManualTaggerSerializer(serializers.ModelSerializer):
    class Meta:
        model = ManualTagger
        fields = ("replay", "game", "user", "url", "level")
