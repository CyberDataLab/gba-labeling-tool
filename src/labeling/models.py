from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone
from django.contrib.sessions.backends.db import SessionStore as DBStore
from django.contrib.sessions.base_session import AbstractBaseSession

class SessionStore(DBStore):
    @classmethod
    def get_model_class(cls):
        return CustomSession

    def save(self, must_create=False):
        print("saving session store")
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        print("caller name:", calframe[1][3])
        print("save details:" + str(self.__dict__))
        super().save(must_create)

class Game(models.Model):
    name = models.CharField(primary_key=True, max_length=50)
    typeReplay = models.TextField(null=False, blank=False) 

class Level(models.Model):
    game = models.ForeignKey(Game, null = True, on_delete=models.SET_NULL)
    filename = models.CharField(max_length=50, unique=True)
    data = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.filename
    
class URL(models.Model):
    name = models.CharField(max_length=50, null = True)
    game = models.ForeignKey("Game", null = True, on_delete=models.SET_NULL)
    data = models.TextField(null=True, blank=True)
    useGuests = models.BooleanField(default=False)
    levels = models.ForeignKey(
        "Level", blank=True, null=True, on_delete=models.SET_NULL
    )
    process = models.BooleanField(default=False)
    def __str__(self):
        return self.name


class Player(models.Model):
    name = models.CharField(max_length=50)
    url = models.ForeignKey("URL", null=True, on_delete=models.SET_NULL)
    game = models.ForeignKey("Game", null = True, on_delete=models.SET_NULL)
    attempted = models.ManyToManyField(
        "Level", blank=True, related_name="levels_attempted"
    )
    completed = models.ManyToManyField(
        "Level", blank=True, related_name="levels_completed"
    )

    def __str__(self):
        return self.name
        
class ReplayBasic(models.Model):
    replay = models.TextField(null=True, blank=True)
    last_updated = models.DateTimeField(default=timezone.now)
    game = models.ForeignKey(Game, null = True, on_delete=models.SET_NULL)
    user = models.ForeignKey("Player", null=True, on_delete=models.SET_NULL)
    url = models.ForeignKey("URL", null=True, on_delete=models.SET_NULL)
    level = models.ForeignKey(Level, null=True, on_delete=models.SET_NULL)
    firstEvent = models.ForeignKey("Event", null = True, on_delete=models.SET_NULL)
    sequence_order = models.IntegerField(null = True)
    features = models.TextField(null=True)
    
    def __str__(self):
        return self.replay
          
class Event(models.Model):
    time = models.DateTimeField(default=timezone.now)
    user = models.ForeignKey(Player, null = True, on_delete=models.CASCADE) # index on user
    session = models.TextField(null = True)
    replay = models.ForeignKey("ReplayBasic", null=True, on_delete=models.SET_NULL)
    type = models.CharField(max_length=32)
    data = models.TextField()

    def __str__(self):
        session = str(self.session) if self.session else "no_session"
        time = str(self.time) if self.time else "no_time"
        type = str(self.type) if self.type else "no_type"
        data = str(self.data) if self.data else "no_data"
        id = str(self.id) if self.id else "no_id"
        return session + ";" + time + ";" + type + ";" + data + ";" + id

class ManualTagger(models.Model):
    username = models.CharField(primary_key=True, max_length=100)
    levelsTagged = models.ManyToManyField(
        ReplayBasic, blank=True, related_name="replays_tagged"
    )
    def __str__(self):
        return self.username
        
class CustomEvent(models.Model):
    manualTagger = models.ForeignKey("ManualTagger", null = True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=50, null=True)
    regex = models.TextField(null=True, blank=True)
    game = models.ForeignKey("Game", null = True, on_delete = models.SET_NULL)
    
class EventAlias(models.Model):
    manualTagger = models.ForeignKey("ManualTagger", null = True, on_delete=models.SET_NULL)
    game = models.ForeignKey("Game", null = True, on_delete = models.SET_NULL) 
    originalName = models.TextField(null=True)
    alias = models.TextField(null=True)

class Competence(models.Model):
    name = models.CharField(primary_key=True, max_length=50)
    options = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return self.name
        
class Typetag(models.Model):
    type = models.CharField(primary_key=True, max_length=50)
    #Global
    #TimeAnnotated
    #TimeWindow
    
    def __str__(self):
        return self.name
               
class Tag(models.Model):
    manualTagger = models.ForeignKey(ManualTagger, null=False, on_delete=models.CASCADE)
    replay = models.ForeignKey(ReplayBasic, null = False, on_delete=models.CASCADE)
    competence = models.ForeignKey(Competence, null = False, on_delete=models.CASCADE)
    typeTag = models.ForeignKey(Typetag, null = True, on_delete=models.CASCADE)
    tag = models.TextField(null = True, blank=True)
    annotationTime = models.FloatField(null = True)
    finalAnnotationTime = models.FloatField(null = True)
    # If annotationTime and finalAnnotationTime is null, we assume it's a global annotation
    # If finalAnnotationTime is null, it's a single point in time annotation.
    
    def __str__(self):
        return self.replay.replay + self.competence.name + self.tag
    
class Replay(models.Model):
    replay = models.TextField(null=True, blank=True)
    created = models.DateTimeField(default=timezone.now)
    last_updated = models.DateTimeField(default=timezone.now)
    player = models.ForeignKey("Player", null=True, on_delete=models.SET_NULL)
    url = models.ForeignKey("URL", null=True, on_delete=models.SET_NULL)
    level = models.ForeignKey(Level, null=True, on_delete=models.SET_NULL)
    event_range = ArrayField(models.IntegerField(), null=True)
    replay_start_time = models.DateTimeField(blank=True, null=True)
    
    def __str__(self):
        return self.replay
