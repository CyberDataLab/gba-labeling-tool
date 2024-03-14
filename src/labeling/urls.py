from django.urls import path, re_path
from django.views.generic import RedirectView
from labeling.utils import get_level_json, get_replay_json
from . import views
from core.settings import HOMEPAGE

urlpatterns = [
    path("play/", views.play_game),
    path("addCompetence/", views.add_competence, name="addCompetence"),
    re_path(r"^viewReplay/(?P<game>[a-zA-Z0-9-_%.~ ]+)/(?P<group>[a-zA-Z0-9-_%.~ ]+)/(?P<user>[a-zA-Z0-9-_%.~ ]+)/(?P<slug>[a-zA-Z0-9-_%.~ ]+)", views.generate_replay),
    re_path(r"^get_options/(?P<slug>[a-zA-Z0-9-_%.~ ]+)", views.get_options_competence),
    #re_path(r"^removeCompetence/(?P<slug>[a-zA-Z0-9-_%.~ ]+)", views.remove_competence),
    path("removeCustomEvents/", views.removeCustomEvents),
    path("removeEventsAlias/", views.removeAliasEvents),
    path("addTag/", views.add_tag),
    path("createCustomEvent/", views.createCustomEvent),
    path("createAliasEvent/", views.createAliasEvent),
    path("getCollapsedEvents/", views.parse_events_collapsed),
    path("getTextReplayCustom/", views.parseEventsToTextCustom),
    path("generateOutput/", views.generate_output),
    path("getReplayPlot/", views.parseSequenceWithinLevels),
    path("tag", views.selectGame, name='tag'),
    re_path(r"^allfeatures/(?P<game>[a-zA-Z0-9-_%.~ ]+)", views.export_features),
    re_path(r"^selectGame/(?P<slug>[a-zA-Z0-9-_%.~ ]+)", views.selectGroup),
    re_path(r"^addCustomEvents/(?P<game>[a-zA-Z0-9-_%.~ ]+)", views.addCustomEvents),
    re_path(r"^renameEvents/(?P<game>[a-zA-Z0-9-_%.~ ]+)", views.renameEvents),
    re_path(r"^selectGroup/(?P<game>[a-zA-Z0-9-_%.~ ]+)/(?P<group>[a-zA-Z0-9-_%.~ ]+)",
    views.selectUser),
    re_path(r"^selectUser/(?P<game>[a-zA-Z0-9-_%.~ ]+)/(?P<group>[a-zA-Z0-9-_%.~ ]+)/(?P<slug>[a-zA-Z0-9-_%.~ ]+)", views.selectReplay),
    re_path(r"^createTypetag/(?P<typeTag>[a-zA-Z0-9-_%.~ ]+)", views.create_Typetag),
    path("loadReplays/", views.replayLoader),
    path("login/", views.login),
    path("", RedirectView.as_view(url=HOMEPAGE)),
]
