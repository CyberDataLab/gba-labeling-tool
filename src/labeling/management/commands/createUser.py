from labeling.models import ManualTagger, Typetag
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.utils.crypto import get_random_string
import random
import sys

class Command(BaseCommand):
    help = 'Create a user to label'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username for the new user')

    def handle(self, *args, **kwargs):
        username = kwargs['username']
        
        # Create a new user with the provided username
        user, created = ManualTagger.objects.get_or_create(username=username)
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'User "{username}" created successfully.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'User "{username}" already exists.'))
