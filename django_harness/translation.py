class FallbackQuerysetMixin(object):
    @classmethod
    def fallback_queryset(klass, using=None):
        """
        Provide a Queryset accessor that, if there's no translation for the
        current language, searches the other languages in settings.LANGUAGES
        in order, until it finds a translation.
        """

        # Do that by permuting the fallback list, moving the current language
        # to the beginning.
        from django.conf import settings
        all_fallbacks = [code for code, name in settings.LANGUAGES]

        from django.utils.translation import get_language
        current_lang = get_language()

        try:
            all_fallbacks.remove(current_lang)
        except ValueError:
            raise ValueError("The active language %s is not in the list of "
                "configured languages: %s" % (current_lang, all_fallbacks))

        all_fallbacks.insert(0, current_lang)

        # Assume that there's a manager called 'fallback' on this klass
        return klass.fallback.use_fallbacks(*all_fallbacks)


class UnicodeNameMixin(object):
    def __unicode__(self):
        return unicode(self.name)

# Custom versions of Hvad FallbackQueryset and TranslationFallbackManager
# that precache translations when loading objects, and fall back through
# translations in the best possible order, the one used above.

from hvad.manager import FallbackQueryset, TranslationAwareQueryset


class SmartFallbackQueryset(FallbackQueryset, TranslationAwareQueryset):
    def __init__(self, *args, **kwargs):
        """
        Provide a Queryset accessor that, if there's no translation for the
        current language, searches the other languages in settings.LANGUAGES
        in order, until it finds a translation.
        """

        super(SmartFallbackQueryset, self).__init__(*args, **kwargs)

        # Do that by permuting the fallback list, moving the current language
        # to the beginning.
        from django.conf import settings
        ordered_fallbacks = [code for code, name in settings.LANGUAGES]

        from django.utils.translation import get_language
        current_lang = get_language()

        try:
            ordered_fallbacks.remove(current_lang)
        except ValueError:
            raise ValueError("The active language %s is not in the list of "
                "configured languages: %s" % (current_lang, ordered_fallbacks))

        ordered_fallbacks.insert(0, current_lang)

        self._translation_fallbacks = ordered_fallbacks

    # Hopefully fix Hvad issue 140, which prevented viewing the Events page:
    # https://github.com/KristianOellegaard/django-hvad/issues/140
    def _recurse_q(self, q):
        newchildren = []
        language_joins = []
        # import pdb; pdb.set_trace()
        for child in q.children:
            from django.db.models.query_utils import Q
            if isinstance(child, Q):
                # fixed here
                newq, langjoins = self._recurse_q(child)
                newchildren.append(newq)
            else:
                key, value = child
                # call self.translate() instead of translate()
                newkey, langjoins = self.translate(key, self.model)
                newchildren.append((newkey, value))
            for langjoin in langjoins:
                if langjoin not in language_joins:
                    language_joins.append(langjoin)
        q.children = newchildren
        return q, language_joins

    def in_bulk(self, id_list):
        """
        Hvad doesn't implement in_bulk, but it's not hard, and we need it to
        fill the cache from search results.

        Returns a dictionary mapping each of the given IDs to the object with
        that ID.

        What's wrong with the QuerySet implementation?
        """

        from django.db.models.query import QuerySet
        return QuerySet.in_bulk(self, id_list)

    # Overridden to change one line: call the instance method self.translate()
    # instead of the global function translate(), so that we can modify it.
    def _translate_args_kwargs(self, *args, **kwargs):
        self.language(self._language_code)
        language_joins = []
        newkwargs = {}
        from django.db.models.query_utils import Q
        extra_filters = Q()
        for key, value in kwargs.items():
            # call self.translate() instead of translate()
            newkey, langjoins = self.translate(key, self.model)
            for langjoin in langjoins:
                if langjoin not in language_joins:
                    language_joins.append(langjoin)
            newkwargs[newkey] = value
        newargs = []
        for q in args:
            new_q, langjoins = self._recurse_q(q)
            newargs.append(new_q)
            for langjoin in langjoins:
                if langjoin not in language_joins:
                    language_joins.append(langjoin)
        for langjoin in language_joins:
            extra_filters &= Q(**{langjoin: self._language_code})
        return newargs, newkwargs, extra_filters

    # Overridden to change one line: call the instance method self.translate()
    # instead of the global function translate(), so that we can modify it.
    def _translate_fieldnames(self, fields):
        self.language(self._language_code)
        newfields = []
        from django.db.models.query_utils import Q
        extra_filters = Q()
        language_joins = []
        for field in fields:
            # call self.translate() instead of translate()
            newfield, langjoins = self.translate(field, self.model)
            newfields.append(newfield)
            for langjoin in langjoins:
                if langjoin not in language_joins:
                    language_joins.append(langjoin)
        for langjoin in language_joins:
            extra_filters &= Q(**{langjoin: self._language_code})
        return newfields, extra_filters

    # Copied from hvad/fieldtranslator.py and modified to hopefully workaround
    # https://projects.aptivate.org/issues/4987 (but note that this is not a
    # full solution, see https://projects.aptivate.org/issues/4991 for details)
    def translate(self, querykey, starting_model):
        """
        Translates a querykey starting from a given model to be 'translation aware'.
        """
        bits = querykey.split('__')
        translated_bits = []
        model = starting_model
        language_joins = []
        max_index = len(bits) - 1
        # iterate over the bits
        for index, bit in enumerate(bits):
            from hvad.fieldtranslator import (get_model_info,
                _get_model_from_field, NORMAL, TRANSLATED, TRANSLATIONS)
            model_info = get_model_info(model)

            # if the bit is a QUERY_TERM, just append it to the translated_bits
            from django.db.models.sql.constants import QUERY_TERMS

            if bit in QUERY_TERMS:
                translated_bits.append(bit)

            # same goes for 'normal model' bits
            elif model_info['type'] == NORMAL:
                translated_bits.append(bit)

            # if the bit is on a translated model, check if it's in translated
            # translated or untranslated fields. If it's in translated, inject a
            # lookup via the translations accessor. Also add a language join on this
            # table.
            elif model_info['type'] == TRANSLATED:
                if bit in model_info['translated']:
                    translated_bits.append(model._meta.translations_accessor)

                translated_bits.append(bit)

                # We don't want to restrict the language used in joins, as it
                # interferes with our ability to connect objects using fallback
                # translations (not translated into current language).
                # ignore the first model, since it should already enforce a
                # language
                if index != 0:
                    path = '__'.join(translated_bits + [model._meta.translations_accessor])
                    pass # language_joins.append('%s__language_code' % path)

            # else (if it's a translations table), inject a 'master' if the field is
            # untranslated and add language joins.
            else:
                if bit in model_info['translated']:
                    translated_bits.append(bit)
                else:
                    path = '__'.join(translated_bits)
                    # ignore the first model, since it should already enforce a
                    # language
                    if index != 0:
                        # don't filter on language: see above
                        pass # language_joins.append('%s__language_code' % path)
                    translated_bits.append('master')
                    translated_bits.append(bit)

            # do we really want to get the next model? Is there a next model?
            if index < max_index:
                next = bits[index + 1]
                if next not in QUERY_TERMS:
                    model = _get_model_from_field(model, bit)
        return '__'.join(translated_bits), language_joins


# from hvad.manager import TranslationFallbackManager
from hvad.manager import TranslationManager


class SmartFallbackManager(TranslationManager):
    # We DO want to use this manager for related fields, if it's the default
    # manager for a class that can be linked to (e.g. Language), despite the
    # cost, because otherwise fallbacks don't work on related objects, and
    # they can't be rendered in templates. Tested by
    # test_get_resource_in_different_language.
    use_for_related_fields = True

    def get_query_set(self):
        return SmartFallbackQueryset(self.model, using=self.db)

    def get(self, *args, **kwargs):
        found = super(SmartFallbackManager, self).get(*args, **kwargs)
        translation = self.get_query_set().get(*args, **kwargs)
        setattr(found, found._meta.translations_cache, translation)
        return found

    def get_all_ordered_by_unicode(self, queryset=None):
        """
        Don't sort by name using the database! It results in a join
        to the translation table, and duplicate results, and it's
        hard to filter them out in the backend, especially taking
        fallback translations into account. It's much easier to do
        it in python after we've got the right (possibly fallback)
        translation loaded into each instance. And provided there aren't
        too many results, it's not significant for performance.

        Note: returns a list, not a queryset
        """
        if queryset is None:
            queryset = self.model.objects.all()

        return sorted(queryset, key=self.model.__unicode__)

from hvad.models import TranslatableModel


class SmartTranslatableModel(TranslatableModel):
    class Meta:
        abstract = True

    def translation(self, language):
        """
        Return the translation of this object into a different language,
        if it's not the same as the currently cached one.
        """

        cached_translation = getattr(self, self._meta.translations_cache, None)
        if (cached_translation is not None and
                cached_translation.language_code == language):

            # Already translated into the correct language, nothing to do
            return self
        else:
            # Find an object that is translated into the right language, and
            # return it.
            return self.__class__.objects.language(language).get(pk=self.pk)

"""
from hvad.descriptors import TranslatedAttribute
class SmartTranslatedAttribute(TranslatedAttribute):
    " ""
    Uses the cached translation if available, to avoid making another database
    query and allow the fallback loading logic to work.
    " ""
    def __get__(self, instance, instance_type=None):
        cache = getattr(self, self.opts.translations_cache, None)

        if cache:
            return getattr(cache, self.name)

        return super(SmartTranslatedAttribute, self).__get__(instance, instance_type)

    def __set__(self, instance, value):
        setattr(self.translation(instance), self.name, value)

    def __delete__(self, instance):
        delattr(self.translation(instance), self.name)
"""


class TranslationTestMixin(object):
    def translate_and_save(self, model, **kwargs):
        model.translate('es')
        for field, value in kwargs.iteritems():
            setattr(model, field, value)
        model.save()

    def create_translated(self, model, en_values, es_values):
        instance = model.objects.create(**en_values)
        self.translate_and_save(instance, **es_values)
        return instance

    def create_translated_named(self, model, en_name, es_name):
        return self.create_translated(model, {'name': en_name},
            {'name': es_name})

    def create(self, model, save=True, **kwargs):
        trans_model = model.objects.translations_model
        trans_fields = trans_model._meta.get_all_field_names()

        trans_values = {}
        # copy to avoid changing the dict while iterating over it, which
        # is not allowed.
        field_values_copy = dict(kwargs)
        for field, value in field_values_copy.iteritems():
            if field in trans_fields:
                trans_values[field] = kwargs.pop(field)

        from django_dynamic_fixture import G, N
        if save:
            instance = G(model, **kwargs)
        else:
            instance = N(model, **kwargs)
        instance.translate('en') # allows access to translated fields

        for field in trans_fields:
            if field in ('id', 'language_code'):
                # leave well alone
                pass
            elif field in trans_values:
                setattr(instance, field, trans_values[field])
            else:
                self.counter = self.counter + 1
                setattr(instance, field, "%s %d" % (field, self.counter))

        if save:
            getattr(instance, instance._meta.translations_cache).save()

        return instance


# Work around a bug in creating new TranslatableModel instances on classes
# with Haystack search indexes, because the post_save signal is sent too
# early, before the translation objects are saved, and Haystack can't access
# the translated model attributes and dies painfully.
# https://github.com/KristianOellegaard/django-hvad/issues/139

# We can't just work around this in ModelForm, because it still leaves manual
# creation of TranslatableModel objects as a trap for the unwary developers.

import django.dispatch
try:
    from aptivate_monkeypatch.monkeypatch import patch
    @patch(django.dispatch.Signal, 'send')
    def send(original_function, self, sender, **named):
        responses = []
        if not self.receivers:
            return responses

        receivers_without_haystack = []
        receivers_that_are_haystack = []

        from haystack import signal_processor
        from haystack.signals import RealtimeSignalProcessor
        from django.dispatch import saferef
        expected_saferef = saferef.safeRef(signal_processor.handle_save)

        for r in self.receivers:
            if r[1] == expected_saferef:
                receivers_that_are_haystack.append(r)
            else:
                receivers_without_haystack.append(r)

        self.receivers = receivers_without_haystack + receivers_that_are_haystack
        return original_function(self, sender, **named)
except ImportError as e:
    import logging
    logger = logging.getLogger('django_harness.translation')
    logger.warning('Failed to patch Django signals for haystack: %s', e)


from hvad.admin import TranslatableAdmin
class SmartTranslatableAdmin(TranslatableAdmin):
    pass


def urlencode_utf8(query, doseq=True):
    """
    Django doesn't convert our unicode values to utf-8, but silently
    discards foreign characters instead, which completely breaks filtering
    on them. We need to assume that URLs can be UTF-8 encoded, which seems
    reasonable.
    """
    query_copy = {}
    for key, value in query.iteritems():
        query_copy[key] = value.encode('utf-8')

    try:
        from urllib import urlencode
    except ImportError:
        from urllib.parse import urlencode

    return urlencode(query_copy, doseq)


