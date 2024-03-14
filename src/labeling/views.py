from zipfile import ZipFile
import json
import uuid
import os
import base64
import csv
import pandas as pd
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.db import IntegrityError
from tqdm import tqdm
import re
import ast
from labeling.serializers import TagSerializer
from labeling.models import Level, ReplayBasic, Competence, ManualTagger, Game, Typetag, CustomEvent, EventAlias, URL, Player, Event
from labeling.models import Tag as TagModel
from .utils import format_time
import plotly.graph_objects as go

dictEventsGame = {"CUSTOM.1-BURN_RELEASE": "INGAMEOBJECTACTION", "CUSTOM.2-FLAP_RELEASE": "INGAMEOBJECTACTION",      "BEGIN.0": "BEGIN", "CUSTOM.4-FREE_END": "INGAMEACTION", "CUSTOM.3-MEDITATE_END": "INGAMEACTION", "COMPLETE.0": "COMPLETE", "CUSTOM.5-FUEL_COLLECT": "INGAMEOBJECTACTION",
                  "TUTORIALCOMPLETION": "TUTORIALCOMPLETION", "CUSTOM.4-TUTORIAL_EXIT": "EXIT", "CUSTOM.1-DRAG_TOOL": "INGAMEOBJECTACTION", "CUSTOM.2-DRAG_POLE": "INGAMEOBJECTACTION", "CUSTOM.1-MOLECULE_RELEASE": "INGAMEOBJECTACTION", "CUSTOM.2-MOLECULE_ROTATE": "INGAMEOBJECTACTION", "CUSTOM.3-QUESTIONANSWER": "INGAMEACTION"}

dictFigures = {1: 'cube', 2: 'pyramid', 3: 'ramp',
               4: 'cylinder', 5: 'cone', 6: 'sphere'}


def login(request):

    return render(request, "labeling/login.html")


def selectGame(request):
    games = Game.objects.all()
    list = {}
    n = 1
    for game in games:
        list["game " + str(n)] = game.name
        n += 1

    if request.method == 'POST':
        username = request.POST.get('username')
        usernameObj = ManualTagger.objects.filter(username=username)
        if username:
            if len(usernameObj) > 0:
                # Do something with the username
                response = render(
                    request, "labeling/selectGame.html", {"username": username, "items": list})
                response.set_cookie("username", username)
                return response
            else:
                # Handle case where no username match the db
                return render(request, "labeling/login.html", {"error": 'User does not exist. Please log in with a valid user.'})
        else:
            # Handle case where no username was provided
            return render(request, "labeling/selectGame.html", {"error": 'No user found. Please log in first.', "items": {}})
    username = request.COOKIES.get('username')
    if username:
        return render(request, "labeling/selectGame.html", {"username": username, "items": list})
    else:
        return render(request, "labeling/selectGame.html", {"error": 'No user found. Please log in first.', "items": {}})


def selectGroup(request, slug):
    username = request.COOKIES.get('username')
    if username:
        game = Game.objects.get(name=slug)
        typeReplay = game.typeReplay
        groups = URL.objects.filter(game=slug)
        lista = {}
        n = 1
        for group in groups:
            lista["group " + str(n)] = group.name
            n += 1
        return render(request, "labeling/selectGroup.html", {"username": username, "items": lista, "game": slug, "typeReplay": typeReplay})
    else:
        return render(request, "labeling/selectGroup.html", {"error": 'No user found. Please log in first.', "items": {}})


def selectUser(request, game, group):
    username = request.COOKIES.get('username')
    if username:
        gameObj = Game.objects.get(name=game)
        typeReplay = gameObj.typeReplay
        users = Player.objects.filter(url__name=group, game=game)
        lista = {}
        n = 1
        for user in users:
            lista["user " + str(n)] = user.name
            n += 1
        return render(request, "labeling/selectPlayer.html", {"username": username, "items": lista, "game": game, "group": group, "typeReplay": typeReplay})
    else:
        # Handle case where no username was provided
        return render(request, "labeling/selectPlayer.html", {"error": 'No user found. Please log in first.', "items": {}})


def selectReplay(request, game, group, slug):
    username = request.COOKIES.get('username')
    if username:
        manualTaggerObj = ManualTagger.objects.filter(username=username)[0]
        gameObj = Game.objects.get(name=game)
        typeReplay = request.GET.get('typeReplay', gameObj.typeReplay)
        replays = ReplayBasic.objects.filter(
            user__name=slug, url__name=group, game=game).order_by('sequence_order')
        player = Player.objects.filter(name=slug, url__name=group, game=game)
        listaR = {}
        n = 1
        # Get the list of existing tags to later display the hover effect
        for replay in replays:
            listaExistingTags = TagModel.objects.filter(
                replay=replay, manualTagger=manualTaggerObj)
            idReplay = replay.replay
            # To see already added to the list and not show every tag in this list
            listCompetences = []
            listaR[idReplay] = {
                'sequence_order': replay.sequence_order if replay.sequence_order is not None else "-", 'tags': []}
            n += 1
            for existingTag in listaExistingTags:
                if (existingTag.competence.name not in listCompetences):
                    idTag = existingTag.competence.name + ": " + existingTag.tag
                    listaR[idReplay]['tags'].append(idTag[0:20] + "...")

                    # Only one tag per competence is shown in the list
                    listCompetences.append(existingTag.competence.name)

        # Do something with the username

        lista = TagModel.objects.filter(
            manualTagger=manualTaggerObj, replay__user__name=slug)
        setTagged = set()

        for elem in lista:
            setTagged.add(str(elem.replay))
        if group != "":
            return render(request, "labeling/viewReplayExperimental.html", {"username": username, "items": listaR, "tagged": list(setTagged), "game": game, "group": group, "player": slug, "typeReplay": typeReplay})
        else:
            return render(request, "labeling/viewReplayExperimental.html", {"username": username, "items": listaR, "tagged": list(setTagged), "player": slug, "game": game, "typeReplay": typeReplay})
    else:
        # Handle case where no username was provided
        return render(request, "labeling/viewReplayExperimental.html", {"error": 'No user found. Please log in first.', "items": {}})


def parseRegexCustomEvents(listEventObjects, customEventsList):
    lazy = False
    newListEventObjects = []
    event_list = list(listEventObjects)
    # Given a list of event objects, return another list of objects with the new sequence.
    # define the custom event regex pattern
    for customEv in customEventsList:
        pattern = customEv.regex
        nameEvent = customEv.name
        print(pattern)

        # compile the regex pattern
        regex = re.compile(pattern)

        # iterate through the list of events
        i = 0
        while i < len(event_list):
            # check if the event sequence starting from this event matches the custom event pattern
            j = i
            while j < len(event_list) and not regex.search(" ".join([event.type for event in event_list[i:j+1]])):
                # print(" ".join([event.type for event in event_list[i:j+1]]))
                j += 1

            # print(" ".join([event.type for event in event_list[i:j+1]]))
            # if a matching event sequence was found, replace the events with a single custom event
            if j > i and j != len(event_list):
                if lazy == True:
                    custom_event = Event(
                        time=event_list[i].time,
                        user=event_list[i].user,
                        session=event_list[i].session,
                        replay=event_list[i].replay,
                        type=nameEvent,
                        data=" ".join(
                            [event.data for event in event_list[i:j+1]])
                    )
                    event_list = event_list[:i] + \
                        [custom_event] + event_list[j+1:]
                    i = i + 1
                    j = i
                # Greedy
                else:
                    k = len(event_list) - 1
                    while k > j and not regex.search(" ".join([event.type for event in event_list[i:k+1]])):
                        # print(" ".join([event.type for event in event_list[i:k+1]]))
                        k -= 1
                    # If coincidence, create custom event
                    if k > j:
                        custom_event = Event(
                            time=event_list[i].time,
                            user=event_list[i].user,
                            session=event_list[i].session,
                            replay=event_list[i].replay,
                            type=nameEvent,
                            data=" ".join(
                                [event.data for event in event_list[i:k+1]])
                        )
                        event_list = event_list[:i] + \
                            [custom_event] + event_list[k+1:]
                        i = i + 1
                        j = i
                    else:
                        custom_event = Event(
                            time=event_list[i].time,
                            user=event_list[i].user,
                            session=event_list[i].session,
                            replay=event_list[i].replay,
                            type=nameEvent,
                            data=" ".join(
                                [event.data for event in event_list[i:j+1]])
                        )
                        event_list = event_list[:i] + \
                            [custom_event] + event_list[j+1:]
                        i = i + 1
                        j = i

            # For 1 sequence regex (regex of 1 event)
            # j == i because it's 1 event, but there might be a coincidence
            elif j == i:
                # If lazy and coincidence
                if lazy == True and regex.search(" ".join([event.type for event in event_list[i:j+1]])):

                    custom_event = Event(
                        time=event_list[i].time,
                        user=event_list[i].user,
                        session=event_list[i].session,
                        replay=event_list[i].replay,
                        type=nameEvent,
                        data=" ".join(
                            [event.data for event in event_list[i:j+1]])
                    )
                    event_list = event_list[:i] + \
                        [custom_event] + event_list[j+1:]
                    i = i + 1
                    j = i
                # If greedy and coincidence
                elif lazy == False and regex.search(" ".join([event.type for event in event_list[i:j+1]])):

                    k = len(event_list) - 1
                    while k > j and not regex.search(" ".join([event.type for event in event_list[i:k+1]])):
                        # print(" ".join([event.type for event in event_list[i:k+1]]))
                        k -= 1

                    # If coincidence, create custom event
                    if k > j:
                        custom_event = Event(
                            time=event_list[i].time,
                            user=event_list[i].user,
                            session=event_list[i].session,
                            replay=event_list[i].replay,
                            type=nameEvent,
                            data=" ".join(
                                [event.data for event in event_list[i:k+1]])
                        )
                        event_list = event_list[:i] + \
                            [custom_event] + event_list[k+1:]
                        i = i + 1
                        j = i
                    else:
                        custom_event = Event(
                            time=event_list[i].time,
                            user=event_list[i].user,
                            session=event_list[i].session,
                            replay=event_list[i].replay,
                            type=nameEvent,
                            data=" ".join(
                                [event.data for event in event_list[i:j+1]])
                        )
                        event_list = event_list[:i] + \
                            [custom_event] + event_list[j+1:]
                        i = i + 1
                        j = i

                # else just update indices
                else:
                    i += 1
                    j = i

            else:
                i += 1
                j = i

    return event_list


def parseEventsToText(game, group, user, replayObj, eventsAlias):
    dictEvents = {}
    n = 0
    secAcum = 0
    nCharLine = 0
    listEvents = Event.objects.filter(replay=replayObj).order_by("time")
    firstEvent = listEvents[0]
    stringAttempt = "Player " + user + " started level " + replayObj.level.filename + \
        " with #attempt " + str(replayObj.replay.split("~")[1] + ".\n")
    for event in listEvents:
        if event != firstEvent:
            difSeconds = round(
                (event.time - prevEvent.time).total_seconds(), 2)
            concatenate = "(+" + str(difSeconds) + "s) "
            stringAttempt += concatenate
            nCharLine += len(concatenate)
            secAcum += difSeconds
            dictEvents["Event " + str(n)] = [difSeconds, round(secAcum, 2)]
        else:
            dictEvents["Event " + str(n)] = [0, 0]

        action = event.type
        action = eventsAlias.get(action, action)
        concatenate = action + " -> "
        stringAttempt += concatenate
        nCharLine += len(concatenate)
        if nCharLine > 30:
            stringAttempt += "\n"
            nCharLine = 0
        dictEvents["Event " + str(n)].append(action)

        if "COMPLETE" in event.type:
            stringAttempt += "Level completed.\n"
        prevEvent = event
        n += 1

    index = stringAttempt.rfind("->")
    stringAttempt = stringAttempt[0:index] + stringAttempt[index+2:]
    return (stringAttempt, dictEvents)


def parseEventsToTextCustom(request):

    # Get the data from the request
    data = json.loads(request.body)
    game = data["game"]
    group = data["group"]
    user = data["user"]
    replay = data["replay"]

    username = request.COOKIES.get('username')
    taggerObj, createdUser = ManualTagger.objects.get_or_create(
        username=username,
    )

    # Load the EventsAlias and parse them
    dictAlias = {}
    existingAlias = EventAlias.objects.filter(
        manualTagger=taggerObj, game=game)
    for alias in existingAlias:
        dictAlias[alias.originalName] = alias.alias

    # Specify that is a replay from a concrete user, level and game

    replayObj = ReplayBasic.objects.filter(
        game=game, url__name=group, user__name=user, replay=replay)[0]

    listEvents = Event.objects.filter(replay=replayObj).order_by("time")

    # Get the custom events created by that manual tagger and call the regex function
    customEventsList = CustomEvent.objects.filter(
        game=Game.objects.get(name=game), manualTagger=taggerObj)
    listEvents = parseRegexCustomEvents(listEvents, customEventsList)

    firstEvent = listEvents[0]
    stringAttempt = "Player " + user + " started level " + replayObj.level.filename + \
        " with #attempt " + str(replayObj.replay.split("~")[1] + ".\n")
    nCharLine = 0
    for event in listEvents:
        if event != firstEvent:
            difSeconds = round(
                (event.time - prevEvent.time).total_seconds(), 2)
            concatenate = "(+" + str(difSeconds) + "s) "
            stringAttempt += concatenate
            nCharLine += len(concatenate)

        action = event.type
        action = dictAlias.get(action, action)
        concatenate = action + " -> "
        stringAttempt += concatenate
        nCharLine += len(concatenate)
        if (nCharLine > 30):
            stringAttempt += "\n"
            nCharLine = 0

        if "COMPLETE" in event.type:
            stringAttempt += "Level completed.\n"

        prevEvent = event

    index = stringAttempt.rfind("->")
    stringAttempt = stringAttempt[0:index] + stringAttempt[index+2:]

    return JsonResponse({"textCustom": stringAttempt})


def parse_events_collapsed(request):
    data = json.loads(request.body)
    game = data["game"]
    group = data["group"]
    user = data["user"]
    replay = data["replay"]
    customized = data["customized"]
    replayObj = ReplayBasic.objects.filter(
        game=game, url__name=group, user__name=user, replay=replay)[0]

    username = request.COOKIES.get('username')
    taggerObj, createdUser = ManualTagger.objects.get_or_create(
        username=username,
    )

    dictAlias = {}
    existingAlias = EventAlias.objects.filter(
        manualTagger=taggerObj, game=game)
    for alias in existingAlias:
        dictAlias[alias.originalName] = alias.alias

    # Get the custom events created by that manual tagger and call the regex function
    customEventsList = CustomEvent.objects.filter(
        game=Game.objects.get(name=game), manualTagger=taggerObj)

    listEvents = Event.objects.filter(replay=replayObj).order_by("time")

    if (customized == True):
        listEvents = parseRegexCustomEvents(listEvents, customEventsList)

    listEvents = list(listEvents)
    output_str = "Player " + user + " started level " + replayObj.level.filename + \
        " with #attempt " + str(replayObj.replay.split("~")[1] + ".\n")

    # assuming your list of Event objects is named "events"
    i = 0
    prev_event = None
    repeated_event_count = 1
    time_diff = 0
    time_diff_accumulated = 0
    nCharLine = 0
    for event in listEvents:
        if prev_event is None:
            # first event, only print the action
            # output_str += f"{event.type} performed\n"
            repeated_event_count = 1
        else:
            # calculate time difference between current and previous events
            time_diff = (event.time - prev_event.time).total_seconds()
            if event.type == prev_event.type:
                # this is a repeated event, increase the count and accumulate the time difference
                repeated_event_count += 1
                time_diff_accumulated += time_diff
            else:
                # this is a new event, print the previous event (if any) with accumulated time difference
                if i == 1:
                    action = dictAlias.get(prev_event.type, prev_event.type)
                    concatenate = action + " -> "
                    output_str += concatenate
                    nCharLine += len(concatenate)
                    prev_event = event
                    time_diff_accumulated += time_diff
                    i += 1
                    continue

                action = dictAlias.get(prev_event.type, prev_event.type)
                if repeated_event_count > 1:
                    concatenate = f"(+{time_diff_accumulated:.2f}s) {action} (x{repeated_event_count}) -> "
                    output_str += concatenate
                    nCharLine += len(concatenate)
                else:
                    concatenate = f"(+{time_diff_accumulated:.2f}s) {action} -> "
                    output_str += concatenate
                    nCharLine += len(concatenate)
                # reset the count and accumulated time difference for the new event
                repeated_event_count = 1
                time_diff_accumulated = time_diff
        prev_event = event
        i += 1
        if (nCharLine > 30):
            output_str += "\n"
            nCharLine = 0

    # print the last event (if any) with accumulated time difference
    if prev_event is not None:
        action = dictAlias.get(prev_event.type, prev_event.type)
        if repeated_event_count > 1:
            time_diff_prev = (prev_event.time - listEvents[listEvents.index(
                prev_event) - 1].time).total_seconds() + time_diff_accumulated
            concatenate = f"(+{time_diff_accumulated:.2f}s) {action} (x{repeated_event_count}) -> "
            output_str += concatenate
            nCharLine += len(concatenate)
        else:
            concatenate = f"(+{time_diff:.2f}s) {action} -> "
            output_str += concatenate
            nCharLine += len(concatenate)

    if "COMPLETE" in event.type:

        output_str += "Level completed.\n"

    index = output_str.rfind("->")
    output_str = output_str[0:index] + output_str[index+2:]
    return JsonResponse({"textCollapsed": output_str})

# Load page to add custom events


def addCustomEvents(request, game):
    username = request.COOKIES.get('username')
    manualTagger, created = ManualTagger.objects.get_or_create(
        username=username,
    )
    dictAlias = {}
    existingAlias = EventAlias.objects.filter(
        manualTagger=manualTagger, game=game)
    for alias in existingAlias:
        dictAlias[alias.originalName] = alias.alias

    if username:
        typeEvents = Event.objects.filter(
            replay__game=game).values_list('type', flat=True).distinct()
        for event in typeEvents:
            if event not in dictAlias.keys():
                dictAlias[event] = event
        return render(request, "labeling/addRegex.html", {"items": dictAlias, "game": game})
    else:
        return render(request, "labeling/addRegex.html", {"errorUser": 'No user found. Please log in first.', "items": {}})

# Load page to rename events


def renameEvents(request, game):
    username = request.COOKIES.get('username')
    if username:
        userCreator, created = ManualTagger.objects.get_or_create(
            username=username,
        )
        existingAlias = EventAlias.objects.filter(manualTagger=userCreator)
        typeEvents = Event.objects.filter(
            replay__game=game).values_list('type', flat=True).distinct()
        dictEvents = {}
        for alias in existingAlias:
            dictEvents[alias.originalName] = alias.alias
        return render(request, "labeling/renameEvents.html", {"items": typeEvents, "game": game, "dictAlias": dictEvents})
    else:
        return render(request, "labeling/renameEvents.html", {"errorUser": 'No user found. Please log in first.', "items": {}})


def createAliasEvent(request):
    username = request.COOKIES.get('username')
    userCreator, created = ManualTagger.objects.get_or_create(
        username=username,
    )
    data = json.loads(request.body)
    nameEvent = data["nameEvent"]
    game = data["game"]
    originalEvent = data["originalEvent"]
    if "CUSTOM" in nameEvent:
        return JsonResponse({"error": "Choose another event name."})
    if len(originalEvent) > 0 and len(nameEvent) > 0:

        existingAlias = EventAlias.objects.filter(originalName=originalEvent, game=Game.objects.get(
            name=game), manualTagger=userCreator).first()
        if existingAlias:
            existingAlias.alias = nameEvent
            existingAlias.save()
            return JsonResponse({"originalEvent": originalEvent, "updated": nameEvent})
        else:
            EventAlias.objects.create(alias=nameEvent, originalName=originalEvent, game=Game.objects.get(
                name=game), manualTagger=userCreator)
            return JsonResponse({"originalEvent": originalEvent, "created": nameEvent})

    else:
        print("error")
        return JsonResponse({"error": "Empty event. No alias defined."})


def createCustomEvent(request):
    username = request.COOKIES.get('username')
    userCreator, created = ManualTagger.objects.get_or_create(
        username=username,
    )
    data = json.loads(request.body)
    nameEvent = data["nameEvent"]
    game = data["game"]
    items = data["items"]
    if "CUSTOM" in nameEvent:
        return JsonResponse({"error": "Choose another event name."})
    if len(items) > 0:
        regexStr = (" ").join(items)
        regexStr = "^" + regexStr + "$"
        regexStr = regexStr.replace("(Any )*", "[-\.A-Za-z0-9_ ]*")
        regexStr = regexStr.replace("(Any )+", "[-\.A-Za-z0-9_ ]+")
        regexStr = regexStr.replace("Any", "[-\.A-Za-z0-9_]+")

        # Prevent catastrophic backtracking
        noSpaces = regexStr.replace(" ", "")
        if "+)*" in noSpaces or "*)+" in noSpaces:
            return JsonResponse({"error": "Error in regex. Try another one."})

        regexStr = regexStr.replace(" )+$", " ?)+$")
        regexStr = regexStr.replace(" )*$", " ?)*$")
        regexStr = regexStr.replace(" )+ ", " )+")
        regexStr = regexStr.replace(" )* ", " )*")

        existingEvent = CustomEvent.objects.filter(
            name=nameEvent, game=Game.objects.get(name=game), manualTagger=userCreator).first()
        if existingEvent:
            existingEvent.regex = regexStr
            existingEvent.save()
            return JsonResponse({"eventName": nameEvent, "updated": regexStr})
        else:
            CustomEvent.objects.create(name=nameEvent, regex=regexStr, game=Game.objects.get(
                name=game), manualTagger=userCreator)
            return JsonResponse({"eventName": nameEvent, "created": regexStr})

    else:
        return JsonResponse({"error": "Empty list. No new event created."})


def removeCustomEvents(request):
    CustomEvent.objects.all().delete()
    return render(request, "labeling/login.html")


def removeAliasEvents(request):
    EventAlias.objects.all().delete()
    return render(request, "labeling/login.html")


def parseSequenceWithinLevels(request):
    data = json.loads(request.body)
    game = data["game"]
    group = data["group"]
    user = data["user"]
    replay = data["replay"]
    customized = data["customized"]
    replayObj = ReplayBasic.objects.filter(
        game=game, url__name=group, user__name=user, replay=replay)[0]
    listEvents = Event.objects.filter(replay=replayObj).order_by("time")

    username = request.COOKIES.get('username')
    taggerObj, createdUser = ManualTagger.objects.get_or_create(
        username=username,
    )
    if (customized == True):
        # Get the custom events created by that manual tagger and call the regex function
        customEventsList = CustomEvent.objects.filter(
            game=Game.objects.get(name=game), 			    manualTagger=taggerObj)
        listEvents = parseRegexCustomEvents(listEvents, customEventsList)

    # Load the EventsAlias and parse them
    dictAlias = {}
    existingAlias = EventAlias.objects.filter(
        manualTagger=taggerObj, game=game)
    for alias in existingAlias:
        dictAlias[alias.originalName] = alias.alias

    pathImages = "static/replay/images/"

    initX = 4.5
    initY = -0.5

    # Create figure
    fig = go.Figure()
    i = 1

    # Add title

    fig.update_layout(
        title={
            'text': user + " started level " + replayObj.level.filename + " - Attempt " + str(replayObj.replay.split("~")[1]),
            'y': 0.9,
            'x': 0.5,
            'xanchor': 'center',
            'yanchor': 'top',
            'font_color': "black"})

    #  Add background image
    with open(pathImages+"pizarra.png", "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode()
        # Add the prefix that plotly will want when using the string as source
    encoded_image = "data:image/png;base64," + encoded_string

    fig.add_layout_image(
        dict(
            source=encoded_image,
            xref="x",
            yref="y",
            x=-12,
            y=1,
            sizex=72,
            sizey=38,
            sizing="stretch",
            opacity=1.0,
            layer="above")
    )
    # ELEMS (seconds to show, nameToMakeDictGet, nrepetitions, nameToShow)

    listAction = []
    listEvents = list(listEvents)

    # assuming your list of Event objects is named "events"
    i = 0
    prev_event = None
    repeated_event_count = 1
    time_diff = 0
    time_diff_accumulated = 0

    for event in listEvents:
        if prev_event is None:
            # first event, only print the action
            # output_str += f"{event.type} performed\n"
            repeated_event_count = 1
        else:
            # calculate time difference between current and previous events
            time_diff = (event.time - prev_event.time).total_seconds()
            if event.type == prev_event.type:
                # this is a repeated event, increase the count and accumulate the time difference
                repeated_event_count += 1
                time_diff_accumulated += time_diff
            else:
                # this is a new event, print the previous event (if any) with accumulated time difference
                if i == 1:
                    elem = (0, dictEventsGame.get(prev_event.type,
                            "NEWCUSTOMEVENT"), 1, prev_event.type)
                    listAction.append(elem)
                    prev_event = event
                    time_diff_accumulated += time_diff
                    i += 1
                    continue

                if repeated_event_count > 1:
                    elem = (round(time_diff_accumulated, 2), dictEventsGame.get(
                        prev_event.type, "NEWCUSTOMEVENT"), repeated_event_count, prev_event.type)
                    listAction.append(elem)
                else:
                    elem = (round(time_diff_accumulated, 2), dictEventsGame.get(
                        prev_event.type, "NEWCUSTOMEVENT"), 1, prev_event.type)
                    listAction.append(elem)
                # reset the count and accumulated time difference for the new event
                repeated_event_count = 1
                time_diff_accumulated = time_diff
        prev_event = event
        i += 1

    # print the last event (if any) with accumulated time difference
    if prev_event is not None:
        if repeated_event_count > 1:
            time_diff_prev = (prev_event.time - listEvents[listEvents.index(
                prev_event) - 1].time).total_seconds() + time_diff_accumulated

            elem = (round(time_diff_accumulated, 2), dictEventsGame.get(
                prev_event.type, "NEWCUSTOMEVENT"), repeated_event_count, prev_event.type)
            listAction.append(elem)
        else:
            elem = (round(time_diff_accumulated, 2), dictEventsGame.get(
                prev_event.type, "NEWCUSTOMEVENT"), 1, prev_event.type)
            listAction.append(elem)

    i = 1
    if len(listAction) > 20:
        incrX = 4.5
        incrY = 3.25
        incrAnnNameX = 1
        incrAnnNameY = 2.5
        iconSizeX = 2
        iconSizeY = 2.25
        maxRowElems = 10
        incrAnnSecondsX = 0.75
        incrAnnSecondsY = 1.25
        sizeFontAction = 10
    else:
        incrX = 9.0
        incrY = 6.5
        incrAnnNameX = 2
        incrAnnNameY = 5
        iconSizeX = 4
        iconSizeY = 4.5
        maxRowElems = 5
        incrAnnSecondsX = 1.5
        incrAnnSecondsY = 2.5
        sizeFontAction = 12
    # Create visualization
    for action in listAction:
        print(action[1])
        with open(pathImages+action[1]+".png", "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
            # Add the prefix that plotly will want when using the string as source
        encoded_image = "data:image/png;base64," + encoded_string
        # Add icon
        fig.add_layout_image(
            dict(
                source=encoded_image,
                xref="x",
                yref="y",
                x=initX,
                y=initY,
                sizex=iconSizeX,
                sizey=iconSizeY,
                sizing="stretch",
                opacity=1.0,
                layer="above")
        )

        # Add annotation with name

        fig.add_annotation(
            text=dictAlias.get(action[3], action[3]),
            # The position of the text relative to the image
            x=initX+incrAnnNameX, y=initY-incrAnnNameY,
            showarrow=False,
            font=dict(
                size=sizeFontAction,
                color="black"
            ),
            # Use "paper" coordinates to position the text relative to the whole figure
            xref="x", yref="y",
            align="center"
        )

        # Add annotation with nTimes
        nTimes = action[2]
        if nTimes > 1:
            fig.add_annotation(
                text="x" + str(action[2]),
                x=initX+iconSizeX, y=initY,  # The position of the text relative to the image
                showarrow=False,
                font=dict(
                    size=sizeFontAction,
                    color="black"
                ),
                # Use "paper" coordinates to position the text relative to the whole figure
                xref="x", yref="y",
                align="center"
            )

        # Add annotation with seconds within actions
        timeBetweenAction = 1.5
        if ((initX == 4.5) & (initY == -0.5)):
            seconds = "Begin"
        else:
            seconds = "+" + str(action[0]) + "s"
        fig.add_annotation(
            text=seconds,
            # The position of the text relative to the image
            x=initX-incrAnnSecondsX, y=initY-incrAnnSecondsY,
            showarrow=False,
            font=dict(
                size=sizeFontAction,
                color="black"
            ),
            # Use "paper" coordinates to position the text relative to the whole figure
            xref="x", yref="y",
            align="center"
        )

        i += 1
        initX += incrX
        if (i > maxRowElems):
            i = 1
            initX = 4.5
            initY -= incrY

    fig.update_layout(xaxis_range=[0, 49], yaxis_range=[-28, 1])
    fig.update_layout(template="plotly_white",
                      paper_bgcolor='rgb(233,233,233)')
    fig.update_yaxes(title='y', visible=False, showticklabels=False)
    fig.update_xaxes(title='x', visible=False, showticklabels=False)
    graph = fig.to_html(full_html=False, include_plotlyjs=False,
                        default_width="1200px", default_height="700px")
    context = {'figure': graph}
    return HttpResponse(graph)
    
def generate_replay(request, game, group, user, slug):
    username = request.COOKIES.get('username')
    userObj, createdUser = ManualTagger.objects.get_or_create(
        username=username,
    )
    # Load alias from the database and parse them
    dictAlias = {}
    aliasList = EventAlias.objects.filter(game=game, manualTagger=userObj)
    for alias in aliasList:
        dictAlias[alias.originalName] = alias.alias

    # Specify that is a replay from a concrete user, level and game
    replayObj = ReplayBasic.objects.filter(
        game=game, url__name=group, user__name=user, replay=slug)[0]
    typeReplay = request.GET.get('typeReplay', replayObj.game.typeReplay)
    competences = Competence.objects.all()
    replayFile = slug
    competencesStr = [x.name for x in competences]
    dictParameter = {"username": username, "replay": slug, "competences": competencesStr,
                     "game": game, "replayFile": replayFile, "group": group, "player": user}

    if (typeReplay in ["textReplay", "videoReplay", "audioReplay"]):
        dictParameter["typeReplay"] = typeReplay
        if (typeReplay == "textReplay"):
            stringAttempt, eventsDict = parseEventsToText(
                game, group, user, replayObj, dictAlias)
            dictParameter["textReplay"] = stringAttempt
            dictParameter["eventsDict"] = eventsDict
            print("Features: ")
            print(replayObj.features)
    else:
        listEvents = Event.objects.filter(replay=replayObj).order_by("time")
        serializer = EventSerializer(listEvents, many=True)
        jsonDict = {"events": serializer.data}
        replayFile = "temp.json"
        print("File to replay: " + replayFile)
        # Opening JSON file
        f = open('static/shadowBuildNoLocal/StreamingAssets/temp.json', 'w')
        f.write(json.dumps(jsonDict))
        f.close()
        print("Features: ")
        print(replayObj.features)

    listaPoss = {}
    for competence in competences:
        if competence.options is not None:
            listOptions = competence.options.split(",")
            # dictAllPossibilities[competence.name] = listOptions
            listaPoss[competence.name] = listOptions
        else:
            listaPoss[competence.name] = []
    dictParameter['options'] = listaPoss
    if not replayObj.features is None:
        features = json.loads(replayObj.features)
        if len(features.keys()) > 0:
            features['contextFeatures']['ActiveTime'] = format_time(
                features['contextFeatures']['ActiveTime'])
            features['contextFeatures']['InactiveTime'] = format_time(
                features['contextFeatures']['InactiveTime'])
            features['attemptFeatures']['ActiveTime'] = format_time(
                features['attemptFeatures']['ActiveTime'])
            features['attemptFeatures']['InactiveTime'] = format_time(
                features['attemptFeatures']['InactiveTime'])
            dictParameter['contextFeatures'] = features['contextFeatures']
            dictParameter['attemptFeatures'] = features['attemptFeatures']
    if typeReplay == "ingameReplay":
        return render(request, "labeling/gameURLTag.html", dictParameter)
    else:
        return render(request, "labeling/otherReplays.html", dictParameter)

# Generates export output (csv, json)


def generate_output(request):
    username = request.COOKIES.get('username')
    userObj, createdUser = ManualTagger.objects.get_or_create(
        username=username,
    )

    data = json.loads(request.body)
    outputFormat = data.get("format", None)
    player = data.get("player", None)
    group = data.get("group", None)
    game = data.get("game", None)

    if game is None:
        query = TagModel.objects.filter(manualTagger=userObj)
    elif group is None:
        query = TagModel.objects.filter(
            manualTagger=userObj, replay__game__name=game)
    elif player is None:
        query = TagModel.objects.filter(
            manualTagger=userObj, replay__url__name=group, replay__game__name=game)
    else:
        query = TagModel.objects.filter(
            manualTagger=userObj, replay__url__name=group, replay__game__name=game, replay__user__name=player)

    serializer = TagSerializer(query, many=True)
    data = serializer.data
    for replay in data:
        dictReplay = replay["replay"]
        replayName = dictReplay["replay"]
        game = dictReplay["game"]["name"]
        user = dictReplay["user"]["name"]
        group = dictReplay["url"]["name"]
        replay["replay"] = replayName
        replay["game"] = game
        replay["user"] = user
        replay["level"] = dictReplay["level"]["filename"]
        replay["group"] = group
        replay["competence"] = replay["competence"]["name"]
        replay["typeTag"] = replay["typeTag"]["type"]
        replay["sequence_order"] = dictReplay["sequence_order"]
        # del replay["replay"]
    if outputFormat == "json":
        return JsonResponse({"events": data}, safe=False)
    elif outputFormat == "csv":
        # Create the HttpResponse object with the appropriate CSV header.
        response = HttpResponse(
            content_type="text/csv",
        )

        response["Content-Disposition"] = 'attachment; filename="tags.csv"'

        writer = csv.writer(response)
        writer.writerow(["Competence", "TypeTag", "Tag", "AnnotationTime", "FinalAnnotationTime",
                        "Game", "User", "SequenceOrder", "Level", "Group", "Replay"])
        for tag in data:
            writer.writerow([tag["competence"], tag["typeTag"], tag["tag"], tag["annotationTime"], tag["finalAnnotationTime"],
                            tag["game"], tag["user"], tag["sequence_order"], tag["level"], tag["group"], tag["replay"]])
        return response

# Here we have to load the replay depending on the type of replay.


def get_options_competence(request, slug):
    competence = Competence.objects.filter(name=slug)[0]
    if competence.options is not None:
        return JsonResponse({"options": competence.options.split(",")})
    else:
        return JsonResponse({"options": []})


def create_Typetag(request, typeTag):
    Typetag.objects.get_or_create(type=typeTag)
    return render(request, "labeling/login.html")


def add_tag(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        username = data['username']
        player = data['player']
        group = data['group']
        game = data['game']
        replay = data['replay']
        competence = data['competence']
        tagName = data['tag']
        annotationTime = None
        finalAnnotationTime = None
        if 'annotationTime' in data.keys():
            annotationTime = round(float(data['annotationTime']), 2)
            if 'finalAnnotationTime' in data.keys():
                finalAnnotationTime = round(
                    float(data['finalAnnotationTime']), 2)
        if username == "None":
            return JsonResponse({"errorUser": "No user logged in. Log in first."})

        userObj, createdUser = ManualTagger.objects.get_or_create(
            username=username,
        )
        replayObj, createdReplay = ReplayBasic.objects.get_or_create(game=game,
                                                                     url__name=group,
                                                                     user__name=player,
                                                                     replay=replay,
                                                                     )

        competenceObj, createdCompetence = Competence.objects.get_or_create(
            name=competence,
        )

        typeTagGlobal = Typetag.objects.filter(type="Global")[0]
        typeTagTimeAnnotated = Typetag.objects.filter(type="TimeAnnotated")[0]
        typeTagTimeWindow = Typetag.objects.filter(type="TimeWindow")[0]

        # Global annotation
        if annotationTime is None:
            existingTag = TagModel.objects.filter(
                manualTagger=userObj, replay=replayObj, competence=competenceObj, typeTag=typeTagGlobal)
            if len(existingTag) == 0:
                TagModel.objects.create(manualTagger=userObj, replay=replayObj,
                                        competence=competenceObj, tag=tagName, typeTag=typeTagGlobal)
                return JsonResponse({"tagCreated": [replay, competence, tagName]})
            else:
                existingTag[0].tag = tagName
                existingTag[0].save()
                return JsonResponse({"tagUpdated": [replay, competence, tagName]})

        # Time annotation
        else:
            # Only one time annotation
            if (finalAnnotationTime is None):
                existingTag = TagModel.objects.filter(
                    manualTagger=userObj, replay=replayObj, competence=competenceObj, annotationTime=annotationTime, typeTag=typeTagTimeAnnotated)
            # Time window
            else:
                existingTag = TagModel.objects.filter(manualTagger=userObj, replay=replayObj, competence=competenceObj,
                                                      annotationTime=annotationTime, finalAnnotationTime=finalAnnotationTime, typeTag=typeTagTimeWindow)
            # No existing tags and only one annotation
            if ((len(existingTag) == 0) & (finalAnnotationTime is None)):
                TagModel.objects.create(manualTagger=userObj, replay=replayObj, competence=competenceObj,
                                        tag=tagName, annotationTime=annotationTime, typeTag=typeTagTimeAnnotated)
                return JsonResponse({"tagCreated": [replay, competence, tagName], "annotationTime": annotationTime})
            # No existing tags and two annotations
            elif ((len(existingTag) == 0) & (finalAnnotationTime is not None)):
                TagModel.objects.create(manualTagger=userObj, replay=replayObj, competence=competenceObj, tag=tagName,
                                        annotationTime=annotationTime, finalAnnotationTime=finalAnnotationTime, typeTag=typeTagTimeWindow)
                return JsonResponse({"tagCreated": [replay, competence, tagName], "annotationTime": annotationTime, "finalAnnotationTime": finalAnnotationTime})
            # Existing tag
            else:
                existingTag[0].tag = tagName
                existingTag[0].save()
                if annotationTime is None:
                    return JsonResponse({"tagUpdated": [replay, competence, tagName], "annotationTime": annotationTime})
                elif finalAnnotationTime is not None:
                    return JsonResponse({"tagUpdated": [replay, competence, tagName], "annotationTime": annotationTime, "finalAnnotationTime": finalAnnotationTime})
                else:
                    return JsonResponse({"tagUpdated": [replay, competence, tagName], "annotationTime": annotationTime})


def add_competence(request):

    username = request.COOKIES.get('username')
    competences = Competence.objects.all()
    competencesStr = [x.name for x in competences]
    dictParameter = {"competences": competencesStr}
    if username is None:
        dictParameter["errorUser"] = "No user found. Please, log in first."
    # If it's a post, check if it's a competence or a new tag
    # If it's a new competence, check that it does not exist. Then add it.
    # If it exists, send an error message to be displayed.
    # Same with tags
    if request.method == 'POST':
        # New tag
        newTag = request.POST.get("newTagName")
        # New competence
        newCompetence = request.POST.get("newCompetenceName")
        if newCompetence is not None:
            if newCompetence in competencesStr:
                dictParameter["errorCompetenceExisting"] = "Competence already exists! Try a new one."
            elif (newCompetence.strip() == ""):
                dictParameter["errorCompetenceExisting"] = "Insert a valid string"
            # else crear el objeto competencia
            else:
                Competence.objects.create(name=newCompetence)
                dictParameter["successCreatingCompetence"] = "Competence created!"
        else:
            listaTag = newTag.split("~")
            competenceName = listaTag[0]
            tag = listaTag[1]
            # Obtener la competencia que sea filtrando en vez de recorrerlas todas
            competence = Competence.objects.filter(name=competenceName)[0]
            # Ahora mismo es = None siempre. Tenemos que ver que cuando sea None, hacer un update con el options incluyendo la tag nueva.
            if (competence.options is not None) & (tag.strip() != ""):
                # Cuando sea none, update al objeto competencia con el nuevo options
                # Cuando no sea none, entonces comprobar que no exista. Si no existe, update pero concatenando con lo que ya habia
                listOptions = competence.options.split(",")
                if tag in listOptions:
                    dictParameter["errorTagExisting"] = "Tag already exists! Try a new one"
                else:
                    dictParameter["successCreatingTag"] = "Tag created!"
                    # Update con el objeto
                    currentOptions = competence.options
                    competence.options = currentOptions + "," + tag
                    competence.save()
            else:
                if (tag.strip() != ""):
                    dictParameter["successCreatingTag"] = "Tag created!"
                    competence.options = tag
                    competence.save()
                else:
                    dictParameter["errorTagExisting"] = "Insert a valid string"
    return render(request, "labeling/addCompetence.html", dictParameter)


def create_competence(request, competence):
    Competence.objects.create(name=competence)
    return render(request, "labeling/login.html")


def remove_competence(request, slug):
    Competence.objects.get(name=slug).delete()
    return render(request, "labeling/login.html")


def play_game(request):
    return render(request, "labeling/gameURL.html")


def preprocessGameData(dataEventsPath, gameId):
    dirPath = os.path.dirname(os.path.abspath(dataEventsPath))
    activityThreshold = 30
    if gameId.lower() == "shadowspect":
        typeEvents = ['ws-snapshot', 'ws-paint', 'ws-rotate_view', 'ws-move_shape', 'ws-rotate_shape', 'ws-scale_shape',
                      'ws-create_shape', 'ws-delete_shape', 'ws-undo_action', 'ws-redo_action', 'ws-check_solution']
        dataEvents = pd.read_csv(dataEventsPath, sep=";")
        dataEvents['group'] = [json.loads(x)['group'] if 'group' in json.loads(
            x).keys() else '' for x in dataEvents['data']]
        dataEvents['user'] = [json.loads(x)['user'] if 'user' in json.loads(
            x).keys() else '' for x in dataEvents['data']]
        # removing those rows where we dont have a group and a user that is not guest
        dataEvents = dataEvents[((dataEvents['group'] != '') & (
            dataEvents['user'] != '') & (dataEvents['user'] != 'guest'))]
        # Data Cleaning
        dataEvents['time'] = pd.to_datetime(dataEvents['time'])
        dataEvents = dataEvents.sort_values('time')

        # To store events from current attempt
        currentAttempt = []
        # Generated files to be written into json
        listGeneratedFiles = []
        newDfEvents = []
        dictFeatures = {}
        skipEvents = ['ws-create_user', 'ws-login_user',
                      'ws-exit_to_menu', 'ws-start_level']
        for group in set(dataEvents['group']):
            groupEvents = dataEvents[dataEvents['group'] == group]
            for user in tqdm(set(groupEvents['user'])):
                # User context features
                activeTimeUser = 0
                inactiveTimeUser = 0
                activeTimeAttempt = 0
                inactiveTimeAttempt = 0
                interactionEvents = 0
                createFigureEvents = 0
                rotateFigureEvents = 0
                moveFigureEvents = 0
                scaleFigureEvents = 0
                deleteFigureEvents = 0
                rotateViewEvents = 0
                completedLevels = 0
                dictUsedFigures = {'cube': 0, 'pyramid': 0,
                                   'ramp': 0, 'cylinder': 0, 'cone': 0, 'sphere': 0}
                snapshots = 0
                timestampSnapshots = []
                checkSolution = 0
                userId = group + "~" + user
                userEvents = groupEvents[groupEvents['user'] == user]
                dictAttempt = {}
                listCompleted = []
                dictAttempt['Global'] = 1
                activePuzzle = None
                previousEvent = None
                completed = False
                total_rows = len(userEvents)
                for enum, event in userEvents.iterrows():
                    if not (activePuzzle is None):
                        if activePuzzle != "Sandbox":
                            currentAttempt.append(event)

                    # Set activePuzzle
                    if (event['type'] == 'ws-start_level'):
                        activePuzzle = json.loads(event['data'])['task_id']
                        if activePuzzle not in dictAttempt.keys() and activePuzzle != "Sandbox":
                            dictAttempt[activePuzzle] = 1
                    elif (event['type'] == 'ws-puzzle_complete'):
                        completed = True
                        listCompleted.append(activePuzzle)

                    # While activePuzzle == Sandbox, continue without processing
                    if activePuzzle == "Sandbox":
                        continue

                    # Update active time
                    if not (previousEvent is None) and not event["type"] in skipEvents:
                        # Duration of event
                        delta_seconds = (
                            event['time'] - previousEvent['time']).total_seconds()
                        if (delta_seconds > activityThreshold):
                            inactiveTimeAttempt += delta_seconds
                        else:
                            activeTimeAttempt += delta_seconds
                    if event['type'] in typeEvents:
                        interactionEvents += 1
                        if event['type'] == 'ws-create_shape':
                            createFigureEvents += 1
                            shape_id = json.loads(event['data'])[
                                'objSerialization']
                            shape_type = json.loads(event['data'])['shapeType']
                            dictUsedFigures[dictFigures[shape_type]] += 1
                        elif event['type'] == 'ws-rotate_shape':
                            rotateFigureEvents += 1
                        elif event['type'] == 'ws-move_shape':
                            moveFigureEvents += 1
                        elif event['type'] == 'ws-scale_shape':
                            scaleFigureEvents += 1
                        elif event['type'] == 'ws-delete_shape':
                            deleteFigureEvents += 1
                        elif event['type'] == 'ws-rotate_view':
                            rotateViewEvents += 1
                        elif event['type'] == 'ws-snapshot':
                            snapshots += 1
                            timestampSnapshots.append(
                                round(activeTimeAttempt + inactiveTimeAttempt, 2))
                        elif event['type'] == 'ws-check_solution':
                            checkSolution += 1

                    if activePuzzle is not None:
                        if activePuzzle in dictAttempt.keys():
                            event['attempt'] = dictAttempt[activePuzzle]
                            event['sequence'] = dictAttempt['Global']
                        event['level'] = activePuzzle
                    else:
                        event['level'] = None
                        event['attempt'] = 1
                        event['sequence'] = 1

                    newDfEvents.append(event)

                    if event['type'] in ['ws-exit_to_menu', 'ws-disconnect', 'ws-login_user'] and enum != total_rows-1:
                        # If puzzle is found
                        if activePuzzle in dictAttempt.keys():
                            # Create attempt features dict
                            idAttempt = event['group'] + "~" + event['user'] + \
                                "~" + event['level'] + "~" + \
                                str(event['attempt'])
                            dictFeatures[idAttempt] = {
                                'contextFeatures': dict(), 'attemptFeatures': dict()}

                            # Save features
                            dictFeatures[idAttempt]['contextFeatures']['#Attempt'] = dictAttempt[activePuzzle]
                            dictFeatures[idAttempt]['contextFeatures']['#GlobalAttempt'] = dictAttempt['Global']
                            activeTimeUser += activeTimeAttempt
                            dictFeatures[idAttempt]['contextFeatures']['ActiveTime'] = activeTimeUser
                            inactiveTimeUser += inactiveTimeAttempt
                            dictFeatures[idAttempt]['contextFeatures']['InactiveTime'] = inactiveTimeUser
                            dictFeatures[idAttempt]['contextFeatures']['CompletedLevels'] = len(
                                set(listCompleted))

                            dictFeatures[idAttempt]['attemptFeatures']['ActiveTime'] = activeTimeAttempt
                            dictFeatures[idAttempt]['attemptFeatures']['InactiveTime'] = inactiveTimeAttempt
                            dictFeatures[idAttempt]['attemptFeatures']['InteractionEvents'] = interactionEvents
                            dictFeatures[idAttempt]['attemptFeatures']['CreateShape'] = createFigureEvents
                            dictFeatures[idAttempt]['attemptFeatures']['UsedFigures'] = dictUsedFigures
                            dictFeatures[idAttempt]['attemptFeatures']['RotateShape'] = rotateFigureEvents
                            dictFeatures[idAttempt]['attemptFeatures']['MoveShape'] = moveFigureEvents
                            dictFeatures[idAttempt]['attemptFeatures']['ScaleShape'] = scaleFigureEvents
                            dictFeatures[idAttempt]['attemptFeatures']['DeleteFigure'] = deleteFigureEvents
                            dictFeatures[idAttempt]['attemptFeatures']['RotateView'] = rotateViewEvents
                            dictFeatures[idAttempt]['attemptFeatures']['Snapshots'] = snapshots
                            dictFeatures[idAttempt]['attemptFeatures']['TimeStampSnapshots'] = timestampSnapshots
                            dictFeatures[idAttempt]['attemptFeatures']['CheckSolution'] = checkSolution
                            dictFeatures[idAttempt]['attemptFeatures']['Completed'] = completed

                            # Update attempts
                            dictAttempt[activePuzzle] += 1
                            dictAttempt['Global'] += 1

                        activePuzzle = None
                        currentAttempt = []
                        dictUsedFigures = {
                            'cube': 0, 'pyramid': 0, 'ramp': 0, 'cylinder': 0, 'cone': 0, 'sphere': 0}
                        # Reset features
                        timestampSnapshots = []
                        activeTimeAttempt = 0
                        inactiveTimeAttempt = 0
                        interactionEvents = 0
                        createFigureEvents = 0
                        rotateFigureEvents = 0
                        moveFigureEvents = 0
                        scaleFigureEvents = 0
                        deleteFigureEvents = 0
                        rotateViewEvents = 0
                        snapshots = 0
                        checkSolution = 0
                        completed = False
                        previousEvent = None
                    else:
                        # Update previous event
                        previousEvent = event

                # Last attempt
                if activePuzzle in dictAttempt.keys():
                    # Create attempt features dict
                    idAttempt = event['group'] + "~" + event['user'] + \
                        "~" + event['level'] + "~" + str(event['attempt'])
                    dictFeatures[idAttempt] = {
                        'contextFeatures': dict(), 'attemptFeatures': dict()}

                    # Save features
                    dictFeatures[idAttempt]['contextFeatures']['#Attempt'] = dictAttempt[activePuzzle]
                    dictFeatures[idAttempt]['contextFeatures']['#GlobalAttempt'] = dictAttempt['Global']
                    activeTimeUser += activeTimeAttempt
                    dictFeatures[idAttempt]['contextFeatures']['ActiveTime'] = activeTimeUser
                    inactiveTimeUser += inactiveTimeAttempt
                    dictFeatures[idAttempt]['contextFeatures']['InactiveTime'] = inactiveTimeUser
                    dictFeatures[idAttempt]['contextFeatures']['CompletedLevels'] = len(
                        set(listCompleted))

                    dictFeatures[idAttempt]['attemptFeatures']['ActiveTime'] = activeTimeAttempt
                    dictFeatures[idAttempt]['attemptFeatures']['InactiveTime'] = inactiveTimeAttempt
                    dictFeatures[idAttempt]['attemptFeatures']['InteractionEvents'] = interactionEvents
                    dictFeatures[idAttempt]['attemptFeatures']['CreateShape'] = createFigureEvents
                    dictFeatures[idAttempt]['attemptFeatures']['UsedFigures'] = dictUsedFigures
                    dictFeatures[idAttempt]['attemptFeatures']['RotateShape'] = rotateFigureEvents
                    dictFeatures[idAttempt]['attemptFeatures']['MoveShape'] = moveFigureEvents
                    dictFeatures[idAttempt]['attemptFeatures']['ScaleShape'] = scaleFigureEvents
                    dictFeatures[idAttempt]['attemptFeatures']['DeleteFigure'] = deleteFigureEvents
                    dictFeatures[idAttempt]['attemptFeatures']['RotateView'] = rotateViewEvents
                    dictFeatures[idAttempt]['attemptFeatures']['Snapshots'] = snapshots
                    dictFeatures[idAttempt]['attemptFeatures']['TimeStampSnapshots'] = timestampSnapshots
                    dictFeatures[idAttempt]['attemptFeatures']['CheckSolution'] = checkSolution
                    dictFeatures[idAttempt]['attemptFeatures']['Completed'] = completed

        return pd.DataFrame(newDfEvents), dictFeatures

    else:
        dictFeatures = dict()
        dataEvents = pd.read_csv(dataEventsPath, sep="\t")
        dataEvents = dataEvents[["session_id", "app_id", "timestamp",
                                 "event_name", "event_data", "version", "index"]]
        dataEvents['group'] = "MainGroup"
        dataEvents['timestamp'] = pd.to_datetime(dataEvents['timestamp'])
        dataEvents = dataEvents.sort_values('timestamp')
        dataEvents['level'] = [
            gameId + "-" + str(ast.literal_eval(evento)['level']) for evento in dataEvents['event_data']]
        dataEvents['user'] = [ast.literal_eval(evento)[
            'persistent_session_id'] + "-" + gameId for evento in dataEvents['event_data']]
        dataEventsList = []
        if gameId.lower() == "magnet":
            for user in tqdm(dataEvents['user'].unique()):
                # User context and attempt features
                activeTimeUser = 0
                inactiveTimeUser = 0
                activeTimeAttempt = 0
                inactiveTimeAttempt = 0
                completed = False
                interactionEvents = 0
                defaultEvents = 0
                listCompleted = []

                attempt = 1
                attemptGlobal = 1
                previousEvent = None
                activeLevel = None
                dictAttempt = dict()
                dataUser = dataEvents[dataEvents['user'] == user]
                for enum, event in dataUser.iterrows():
                    if activeLevel != event['level']:
                        # New level. Reset variables and save info from previous
                        if not activeLevel is None:
                            # Save previous attempt features
                            # Create attempt features dict
                            idAttempt = event['group'] + "~" + event['user'] + \
                                "~" + activeLevel + "~" + \
                                str(dictAttempt[activeLevel])
                            dictFeatures[idAttempt] = {
                                'contextFeatures': dict(), 'attemptFeatures': dict()}

                            # Save features
                            dictFeatures[idAttempt]['contextFeatures']['#Attempt'] = dictAttempt[activeLevel]
                            dictFeatures[idAttempt]['contextFeatures']['#GlobalAttempt'] = attemptGlobal
                            activeTimeUser += activeTimeAttempt
                            dictFeatures[idAttempt]['contextFeatures']['ActiveTime'] = activeTimeUser
                            inactiveTimeUser += inactiveTimeAttempt
                            dictFeatures[idAttempt]['contextFeatures']['InactiveTime'] = inactiveTimeUser
                            dictFeatures[idAttempt]['contextFeatures']['CompletedLevels'] = len(
                                set(listCompleted))

                            dictFeatures[idAttempt]['attemptFeatures']['ActiveTime'] = activeTimeAttempt
                            dictFeatures[idAttempt]['attemptFeatures']['InactiveTime'] = inactiveTimeAttempt
                            dictFeatures[idAttempt]['attemptFeatures']['InteractionEvents'] = interactionEvents
                            dictFeatures[idAttempt]['attemptFeatures']['DefaultEvents'] = defaultEvents
                            dictFeatures[idAttempt]['attemptFeatures']['Completed'] = completed

                            attempt += 1
                            attemptGlobal += 1
                            # Reset attempt features
                            activeTimeAttempt = 0
                            inactiveTimeAttempt = 0
                            completed = False
                            interactionEvents = 0
                            defaultEvents = 0
                            prevEvent = None

                        activeLevel = event['level']
                        if activeLevel not in dictAttempt.keys():
                            dictAttempt[activeLevel] = 1
                        else:
                            dictAttempt[activeLevel] += 1

                    if "CUSTOM" in event['event_name']:
                        p = re.compile('(?<!\\\\)\'')
                        eventData = event["event_data"]
                        eventData = p.sub('\"', eventData)
                        eventData = eventData.replace("None", "\"None\"")
                        eventData = eventData.replace("True", "true")
                        eventData = eventData.replace("False", "false")
                        dataJson = json.loads(eventData)
                        event['event_name'] = event['event_name'] + \
                            '-' + dataJson['event_custom']
                        # feature count
                        eventType = dictEventsGame.get(
                            event['event_name'], "DEFAULT")
                        if eventType in ["INGAMEOBJECTACTION", "INGAMEACTION"]:
                            interactionEvents += 1
                        elif eventType == "DEFAULT":
                            defaultEvents += 1
                    elif "COMPLETE" in event['event_name']:
                        completed = True
                        listCompleted.append(activeLevel)

                    if not previousEvent is None:
                        # Duration of event
                        delta_seconds = (
                            event['timestamp'] - previousEvent['timestamp']).total_seconds()
                        if (delta_seconds > activityThreshold):
                            inactiveTimeAttempt += delta_seconds
                        else:
                            activeTimeAttempt += delta_seconds

                    if not activeLevel is None:
                        event['attempt'] = dictAttempt[activeLevel]
                        event['sequence'] = attemptGlobal
                        dataEventsList.append(event)
                        previousEvent = event
                # Last event, add features
                # Create attempt features dict
                if not activeLevel is None:
                    idAttempt = event['group'] + "~" + event['user'] + \
                        "~" + event['level'] + "~" + str(event['attempt'])
                    dictFeatures[idAttempt] = {
                        'contextFeatures': dict(), 'attemptFeatures': dict()}

                    # Save features
                    if activeLevel not in dictAttempt.keys():
                        dictAttempt[activeLevel] = 1
                    dictFeatures[idAttempt]['contextFeatures']['#Attempt'] = dictAttempt[activeLevel]
                    dictFeatures[idAttempt]['contextFeatures']['#GlobalAttempt'] = attemptGlobal
                    activeTimeUser += activeTimeAttempt
                    dictFeatures[idAttempt]['contextFeatures']['ActiveTime'] = activeTimeUser
                    inactiveTimeUser += inactiveTimeAttempt
                    dictFeatures[idAttempt]['contextFeatures']['InactiveTime'] = inactiveTimeUser
                    dictFeatures[idAttempt]['contextFeatures']['CompletedLevels'] = len(
                        set(listCompleted))

                    dictFeatures[idAttempt]['attemptFeatures']['ActiveTime'] = activeTimeAttempt
                    dictFeatures[idAttempt]['attemptFeatures']['InactiveTime'] = inactiveTimeAttempt
                    dictFeatures[idAttempt]['attemptFeatures']['InteractionEvents'] = interactionEvents
                    dictFeatures[idAttempt]['attemptFeatures']['DefaultEvents'] = defaultEvents
                    dictFeatures[idAttempt]['attemptFeatures']['Completed'] = completed
        else:
            for user in tqdm(dataEvents['user'].unique()):
                # User context and attempt features
                activeTimeUser = 0
                inactiveTimeUser = 0
                activeTimeAttempt = 0
                inactiveTimeAttempt = 0
                completed = False
                interactionEvents = 0
                defaultEvents = 0
                dictAttempt = dict()
                activeLevel = None
                listCompleted = []
                previousEvent = None
                attempt = 1
                attemptGlobal = 1
                dataUser = dataEvents[dataEvents['user'] == user]
                for enum, event in dataUser.iterrows():
                    if event['event_name'] == 'BEGIN.0':
                        if not activeLevel is None:
                            # Save previous attempt features
                            # Create attempt features dict
                            idAttempt = event['group'] + "~" + event['user'] + \
                                "~" + activeLevel + "~" + \
                                str(dictAttempt[activeLevel])
                            dictFeatures[idAttempt] = {
                                'contextFeatures': dict(), 'attemptFeatures': dict()}

                            # Save features
                            dictFeatures[idAttempt]['contextFeatures']['#Attempt'] = dictAttempt[activeLevel]
                            dictFeatures[idAttempt]['contextFeatures']['#GlobalAttempt'] = attemptGlobal
                            activeTimeUser += activeTimeAttempt
                            dictFeatures[idAttempt]['contextFeatures']['ActiveTime'] = activeTimeUser
                            inactiveTimeUser += inactiveTimeAttempt
                            dictFeatures[idAttempt]['contextFeatures']['InactiveTime'] = inactiveTimeUser
                            dictFeatures[idAttempt]['contextFeatures']['CompletedLevels'] = len(
                                set(listCompleted))

                            dictFeatures[idAttempt]['attemptFeatures']['ActiveTime'] = activeTimeAttempt
                            dictFeatures[idAttempt]['attemptFeatures']['InactiveTime'] = inactiveTimeAttempt
                            dictFeatures[idAttempt]['attemptFeatures']['InteractionEvents'] = interactionEvents
                            dictFeatures[idAttempt]['attemptFeatures']['DefaultEvents'] = defaultEvents
                            dictFeatures[idAttempt]['attemptFeatures']['Completed'] = completed

                            attempt += 1
                            attemptGlobal += 1
                            # Reset attempt features
                            activeTimeAttempt = 0
                            inactiveTimeAttempt = 0
                            completed = False
                            interactionEvents = 0
                            defaultEvents = 0
                            prevEvent = None

                        activeLevel = event['level']
                        if activeLevel not in dictAttempt.keys():
                            dictAttempt[activeLevel] = 1
                        else:
                            dictAttempt[activeLevel] += 1

                    elif "CUSTOM" in event['event_name']:
                        p = re.compile('(?<!\\\\)\'')
                        eventData = event["event_data"]
                        eventData = p.sub('\"', eventData)
                        eventData = eventData.replace("None", "\"None\"")
                        eventData = eventData.replace("True", "true")
                        eventData = eventData.replace("False", "false")
                        dataJson = json.loads(eventData)
                        event['event_name'] = event['event_name'] + \
                            '-' + dataJson['event_custom']
                        # feature count
                        eventType = dictEventsGame.get(
                            event['event_name'], "DEFAULT")
                        if eventType in ["INGAMEOBJECTACTION", "INGAMEACTION"]:
                            interactionEvents += 1
                        elif eventType == "DEFAULT":
                            defaultEvents += 1
                    elif "COMPLETE" in event['event_name']:
                        completed = True
                        listCompleted.append(activeLevel)

                    if not previousEvent is None:
                        # Duration of event
                        delta_seconds = (
                            event['timestamp'] - previousEvent['timestamp']).total_seconds()
                        if delta_seconds > activityThreshold:
                            inactiveTimeAttempt += delta_seconds
                        else:
                            activeTimeAttempt += delta_seconds

                    if not activeLevel is None:
                        event['attempt'] = dictAttempt[activeLevel]
                        event['sequence'] = attemptGlobal
                        previousEvent = event
                        dataEventsList.append(event)

                # Last event, add features
                # Create attempt features dict
                if not activeLevel is None:
                    idAttempt = event['group'] + "~" + event['user'] + \
                        "~" + event['level'] + "~" + str(event['attempt'])
                    dictFeatures[idAttempt] = {
                        'contextFeatures': dict(), 'attemptFeatures': dict()}

                    # Save features
                    if activeLevel not in dictAttempt.keys():
                        dictAttempt[activeLevel] = 1
                    dictFeatures[idAttempt]['contextFeatures']['#Attempt'] = dictAttempt[activeLevel]
                    dictFeatures[idAttempt]['contextFeatures']['#GlobalAttempt'] = attemptGlobal
                    activeTimeUser += activeTimeAttempt
                    dictFeatures[idAttempt]['contextFeatures']['ActiveTime'] = activeTimeUser
                    inactiveTimeUser += inactiveTimeAttempt
                    dictFeatures[idAttempt]['contextFeatures']['InactiveTime'] = inactiveTimeUser
                    dictFeatures[idAttempt]['contextFeatures']['CompletedLevels'] = len(
                        set(listCompleted))

                    dictFeatures[idAttempt]['attemptFeatures']['ActiveTime'] = activeTimeAttempt
                    dictFeatures[idAttempt]['attemptFeatures']['InactiveTime'] = inactiveTimeAttempt
                    dictFeatures[idAttempt]['attemptFeatures']['InteractionEvents'] = interactionEvents
                    dictFeatures[idAttempt]['attemptFeatures']['DefaultEvents'] = defaultEvents
                    dictFeatures[idAttempt]['attemptFeatures']['Completed'] = completed

        dataEvents = pd.DataFrame(dataEventsList)
        dataEvents = dataEvents.rename(
            columns={"timestamp": "time", "event_data": "data", "event_name": "type"})
        print(dictFeatures)
        return dataEvents, dictFeatures


def checkAudioVideoFormat(fileName, typeReplay):
    if typeReplay == "audioReplay":
        listFormats = ["mp3", "mp4", "wav", "aac"]
    else:
        listFormats = ["mp4", "mov", "flv", "avi", "wmv"]
    for audioVideoFormat in listFormats:
        if audioVideoFormat in fileName:
            return True
    return False


def generateVideoReplays(path, gameId):
    files = os.listdir(path)
    gameObj = Game.objects.filter(name=gameId)[0]
    for elem in files:
        if ("~" in elem) & (os.path.isdir(path+"/"+elem)):
            # If it's a directory from a user
            listGroupUser = elem.split("~")
            group = listGroupUser[0]
            user = listGroupUser[1]
            # Create group if does not exist

            groupObj, created = URL.objects.get_or_create(
                name=group,
                game=gameObj,
                data="",
                useGuests=False,)

            if not created:
                print("Duplicate group: " + group + ". Not adding it.")

            # Try creting the user if does not exist
            userObj, created = Player.objects.get_or_create(
                name=user,
                game=gameObj,
                url=groupObj,
            )

            if not created:
                print("Duplicate user: " + user + ". Not adding it.")

            for video in os.listdir(path+"/"+elem):
                if (((gameObj.typeReplay == "videoReplay") & (checkAudioVideoFormat(video, gameObj.typeReplay))) | ((gameObj.typeReplay == "audioReplay") & (checkAudioVideoFormat(video, gameObj.typeReplay)))):
                    sessionId = "DefaultSession"
                    # Create level if it does not exist
                    puzzle = os.path.splitext(video)[0]
                    puzzleObj, created = Level.objects.get_or_create(
                        filename=puzzle, game=gameObj)
                    if not created:
                        print("Duplicate puzzle: " +
                              puzzle + ". Not adding it.")
                    try:
                        ReplayBasic.objects.create(
                            replay=puzzle,
                            game=gameObj,
                            user=userObj,
                            url=groupObj,
                            level=puzzleObj
                        )
                    except IntegrityError:
                        print("Duplicate replay. Not adding it.")
                        pass


def replayLoader(request):

    if request.method == "POST" and request.FILES["levelbundle"]:
        print("replays loading...")

        levelbundle = request.FILES["levelbundle"]
        zipfile = ZipFile(levelbundle)

        replays = json.loads(zipfile.read("listReplays.json"))
        # print(replays["files"])

        gameId = replays["game"]
        extract_path = "static/replay/replayFiles/" + gameId
        isExist = os.path.exists(extract_path)
        if not isExist:
            # Create a new directory because it does not exist
            os.makedirs(extract_path)

        zipfile.extractall(path=extract_path)

        # Create game if not already created
        typeReplay = replays["typeReplay"]
        gameObj, created = Game.objects.get_or_create(
            name=gameId, typeReplay=typeReplay)

        # Read different files to be processed
        if (typeReplay == "videoReplay") | (typeReplay == "audioReplay"):
            generateVideoReplays(extract_path, gameId)
            return render(
                request,
                "labeling/replayloader.html",
                {"file_uploaded": True},
            )
        else:
            eventFiles = replays["files"]
            # Process each file
            for eventFile in eventFiles:
                dataEvents, dictFeatures = preprocessGameData(
                    extract_path+"/"+eventFile, gameId)

                for group in set(dataEvents['group']):
                    groupEvents = dataEvents[dataEvents['group'] == group]
                    # Create or get group
                    groupObj, created = URL.objects.get_or_create(
                        name=group,
                        game=gameObj,
                        data="",
                        useGuests=False,)
                    if not created:
                        print("Duplicate group: " + group + ". Not adding it.")

                    for user in set(groupEvents['user']):
                        userEvents = groupEvents[groupEvents['user'] == user]
                        # Create or get user
                        userObj, created = Player.objects.get_or_create(
                            name=user,
                            game=gameObj,
                            url=groupObj,
                        )
                        if not created:
                            print("Duplicate user: " +
                                  user + ". Not adding it.")

                        setLevels = set(userEvents['level'])
                        if None in setLevels:
                            setLevels.remove(None)

                        for level in setLevels:
                            # Create or get the level
                            levelEvents = userEvents[userEvents['level'] == level]
                            puzzleObj, created = Level.objects.get_or_create(
                                filename=level, game=gameObj)
                            for attempt in set(levelEvents['attempt']):
                                attemptEvents = levelEvents[levelEvents['attempt'] == attempt]
                                attemptSequenceOrder = attemptEvents[0:1]['sequence']
                                attemptId = group + "~" + user + \
                                    "~" + level + "~" + str(attempt)
                                attemptFeatures = dictFeatures.get(
                                    attemptId, {})
                                nameReplay = level + "~" + str(attempt)
                                replayObj, created = ReplayBasic.objects.get_or_create(
                                    replay=nameReplay,
                                    game=gameObj,
                                    user=userObj,
                                    url=groupObj,
                                    level=puzzleObj,
                                    sequence_order=attemptSequenceOrder,
                                    features = json.dumps(attemptFeatures)
                                )
                                if not created:
                                    print("Duplicate attempt replay: " +
                                          nameReplay + ". Updating it.")
                                    replayObj.features = json.dumps(
                                        attemptFeatures)
                                    replayObj.save()
                                else:
                                    print("Creating replay: " + nameReplay)
                                for enum, event in attemptEvents.iterrows():
                                    Event.objects.get_or_create(time=event['time'], user=userObj, session=str(
                                        event['session_id']), replay=replayObj, type=event['type'], data=event['data'])

        return render(
            request,
            "labeling/replayloader.html",
            {"file_uploaded": True},
        )

    return render(
        request,
        "labeling/replayloader.html",
        {"file_uploaded": False},
    )


def export_features(request, game):
    dictReplays = dict()
    # Extract the "list" parameter from the URL
    filename_list_str = request.GET.get('list', "")
    if len(filename_list_str) > 0:
        filename_list = [filename.strip()
                         for filename in filename_list_str.split(',')]
        replays = ReplayBasic.objects.filter(
            game=game, level__filename__in=filename_list)
    else:
        replays = ReplayBasic.objects.filter(game=game)
    for replay in replays:
        replayKey = replay.game.pk + "~" + replay.user.url.name + "~" + \
            replay.user.name + "~" + replay.level.filename + \
            "~" + str(replay.sequence_order)
        dictReplays[replayKey] = json.loads(replay.features)
    print(dictReplays)
    return JsonResponse(dictReplays)


