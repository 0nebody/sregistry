'''

Copyright (C) 2017-2019 Vanessa Sochat.

This program is free software: you can redistribute it and/or modify it
under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public
License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

'''

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import FileSystemStorage
from django.db.models.signals import post_save
from django.conf import settings
from django.db import models
import uuid
import time
import hashlib
import os

################################################################################
# HELPERS
################################################################################

def get_upload_to(instance, filename):
    filename = os.path.join(settings.UPLOAD_PATH, instance.upload_id + '.simg')
    return time.strftime(filename)

def get_upload_folder(instance, filename):
    '''a helper function to upload to storage
    '''
    from shub.apps.main.models import Container, Collection
    tag = instance.tag.lower()
    collection_name = instance.collection.lower()
    instance.collection = collection_name
    
    # First get a collection
    try:
        collection = Collection.objects.get(name=collection_name)
    except Collection.DoesNotExist:
        collection = Collection.objects.create(name=collection_name)
        collection.secret = str(uuid.uuid4())
        collection.save()

    # Create collection root, if it doesn't exist
    image_home = "%s/%s" %(settings.MEDIA_ROOT,collection_name)
    if not os.path.exists(image_home):
        os.mkdir(image_home)
    
    # Create a container, or get it, if doesn't exist
    return os.path.join(image_home, filename)



################################################################################
# MODELS & STORAGE
################################################################################


class OverwriteStorage(FileSystemStorage):

    def get_available_name(self, name, max_length=None):
        # If the filename already exists, remove it as if it was a true file system
        if self.exists(name):
            os.remove(os.path.join(settings.MEDIA_ROOT, name))
        return name


class ImageFile(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    collection = models.CharField(max_length=200, null=False)
    tag = models.CharField(max_length=200, null=False)
    metadata = models.TextField(default='') # will be converted to json
    name = models.CharField(max_length=200, null=False)
    owner_id = models.CharField(max_length=200, null=True)
    datafile = models.FileField(upload_to=get_upload_folder,
                                max_length=255,
                                storage=OverwriteStorage())

    def get_label(self):
        return "imagefile"

    def get_abspath(self):
        return os.path.join(settings.MEDIA_ROOT, self.datafile.name)

    class Meta:
        app_label = 'api'


################################################################################
# UPLOADS
################################################################################

class ImageUpload(models.Model):
    ''' a base image upload to hold a file temporarily during upload
        based off of django-chunked-uploads BaseChunkedUpload model
    '''

    upload_id = models.CharField(max_length=32, unique=True, editable=False,
                                 default=uuid.uuid4().hex)
    file = models.FileField(max_length=255, upload_to=get_upload_to)
    filename = models.CharField(max_length=255)
    offset = models.BigIntegerField(default=0)
    created_on = models.DateTimeField(auto_now_add=True)
    completed_on = models.DateTimeField(null=True, blank=True)

    @property
    def md5(self):
        if getattr(self, '_md5', None) is None:
            md5 = hashlib.md5()
            for chunk in self.file.chunks():
                md5.update(chunk)
            self._md5 = md5.hexdigest()
        return self._md5

    def delete(self, delete_file=True, *args, **kwargs):
        if self.file:
            storage, path = self.file.storage, self.file.path
        super(ImageUpload, self).delete(*args, **kwargs)
        if self.file and delete_file:
            storage.delete(path)

    class Meta:
        app_label = 'api'
