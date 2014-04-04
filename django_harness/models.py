from __future__ import unicode_literals, absolute_import

from django.db import models

from hvad.models import TranslatableModel, TranslatedFields
from hvad.manager import TranslationManager, TranslationFallbackManager

# doesn't work: https://github.com/KristianOellegaard/django-hvad/issues/44
"""
class SimpleNamedModel(TranslatableModel):
    class Meta:
        abstract = True

    objects = TranslationManager()
    fallback = TranslationFallbackManager()

    translations = TranslatedFields(
        name = models.CharField(max_length=255),
    )

    def __unicode__(self):
        translation_model = self.translations.model

        try:
            return unicode(self.name)
        except translation_model.DoesNotExist as e:
            return unicode(self.__class__.fallback_queryset()[0].name)
"""

