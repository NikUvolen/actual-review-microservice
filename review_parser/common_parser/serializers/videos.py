from rest_framework import serializers
from common_parser.models import Playlist, Video


class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = (
            'id',
            'playlist',
            'external_id',
            'url',
            'title',
            'author',
            'duration_seconds',
            'preview_url',
            'published_date'
        )


class PlaylistSerializer(serializers.ModelSerializer):
    videos = VideoSerializer(many=True, read_only=True)

    class Meta:
        model = Playlist
        fields = (
            'id',
            'organization',
            'title',
            'provider',
            'source_url',
            'external_playlist_id',
            'last_parse_time',
            'videos'
        )
