import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from labeling.models import Level, Replay, URL, Player

def format_time(seconds):
    hours = seconds // 3600
    remaining_seconds = seconds % 3600
    minutes = remaining_seconds // 60
    remaining_seconds = remaining_seconds % 60

    formatted_time = ""

    if hours > 0:
        formatted_time += f"{int(hours)}h "
        if minutes > 0:
            formatted_time += f"{int(minutes)}m"
    elif minutes > 0:
        formatted_time += f"{int(minutes)}m"

    if remaining_seconds > 0 or not formatted_time:
        remaining_seconds = round(remaining_seconds, 1)
        formatted_time += f" {remaining_seconds}s"

    return formatted_time


def get_level_json(request, slug):
    level = Level.objects.get(filename=slug)
    data = json.loads(level.data)
    return JsonResponse(data)


def get_replay_json(request):
    url_name, player, level, attempt = request.session["replay_metadata"]
    url = URL.objects.get(name=url_name)
    player = Player.objects.filter(url=url).get(id=player)

    replays = Replay.objects.filter(
        player=player,
        url=url,
        level=level
    )
    replay_obj = replays[int(attempt)]
    replay_json = json.loads(replay_obj.replay)
    return JsonResponse(replay_json)
