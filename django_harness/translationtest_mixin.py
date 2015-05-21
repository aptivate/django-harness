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


