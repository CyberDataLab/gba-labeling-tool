from labeling.models import ManualTagger, Typetag
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.utils.crypto import get_random_string
import random
import sys

class Command(BaseCommand):
    help = 'Init the db instances'

    def handle(self, *args, **kwargs):
    
        Typetag.objects.get_or_create(type = "Global")
        Typetag.objects.get_or_create(type = "TimeAnnotated")
        Typetag.objects.get_or_create(type = "TimeWindow")
        
        
        self.stdout.write(self.style.SUCCESS(f'Operation successful.'))
