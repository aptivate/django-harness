from __future__ import absolute_import, unicode_literals

import datetime

from django.core.files.base import ContentFile
from django.db.models import Model
from django.forms.widgets import HiddenInput
from django.http.request import QueryDict
import django.forms.widgets

try:
    from captcha.widgets import ReCaptcha
except ImportError as e:
    class ReCaptcha(object):
        pass


class FormUtilsMixin(object):
    def get_possible_values(self, choices):
        possible_values = []
        for choice_value, choice_label in choices:
            # Handle the special case where the value is actually a Model.
            # This is used by SubThemeWidget on RUForum for example, to
            # add extra attributes to the HTML rendered by the widget.
            # In this case, we guess that the PK is the value that's needed.
            if isinstance(choice_value, Model):
                choice_value = choice_value.pk

            if isinstance(choice_label, list) or isinstance(choice_label, tuple):
                # This is actually a group of options, and therefore not
                # selectable, but it contains entries which are.
                possible_values.extend([v for v, label in choice_label])
            else:
                possible_values.append(choice_value)
        return possible_values

    def value_to_datadict(self, widget, name, value, strict=True):
        """
        There's a value_from_datadict method in each django.forms.widgets widget,
        but nothing that goes in the reverse direction, and
        test_utils.AptivateEnhancedTestCase.update_form_values really wants to
        convert form instance values (Python data) into a set of parameters
        suitable for passing to client.post().

        This needs to be implemented for each subclass of Widget that doesn't
        just convert its value to a string.
        """

        import django.forms.widgets
        import django.contrib.admin.widgets
        import django.contrib.auth.forms
        from django.utils.encoding import force_unicode

        if isinstance(widget, django.forms.widgets.FileInput):
            # this is a special case: don't convert FieldFile objects to strings,
            # because the TestClient needs to detect and encode them properly.
            if bool(value):
                return {name: value}
            else:
                # empty file upload, don't set any parameters
                return {}

        elif isinstance(widget, django.forms.widgets.MultiWidget):
            values = {}
            for index, subwidget in enumerate(widget.widgets):
                param_name = "%s_%s" % (name, index)
                values.update(self.value_to_datadict(subwidget, param_name,
                    value, strict))
            return values

        elif isinstance(widget, django.forms.widgets.CheckboxInput):
            if widget.check_test(value):
                return {name: '1'}
            else:
                # unchecked checkboxes are not sent in HTML
                return {}

        elif isinstance(widget, django.forms.widgets.Select):
            if '__iter__' in dir(value):
                values = list(value)
            else:
                values = [value]

            choices = list(widget.choices)
            possible_values = self.get_possible_values(choices)
            found_values = []

            for v in values:
                if v in possible_values:
                    found_values.append(str(v))
                elif v == '' and isinstance(widget, django.forms.widgets.RadioSelect):
                    # It's possible not to select any option in a RadioSelect
                    # widget, although this will probably generate an error
                    # as the field is probably required, but we need to be
                    # able to test that behaviour, by passing an empty string.
                    #
                    # In that case, we don't add anything to the POST data,
                    # because a user agent wouldn't either if the user hasn't
                    # selected any of the radio buttons
                    pass
                elif strict:
                    # Since user agent behaviour differs, authors should ensure
                    # that each menu includes a default pre-selected OPTION
                    # (i.e. that a list includes a selected value)
                    raise Exception("List without selected value: "
                        "%s = %s (should be one of: %s)" %
                        (name, value, [label for label, value in choices]))
                else:
                    # don't add anything to the list right now
                    pass

            if found_values:
                return {name: found_values}
            elif isinstance(widget, django.forms.widgets.RadioSelect):
                # As above, it's possible not to select any option in a
                # RadioSelect widget. In that case, we don't add anything
                # to the POST data.
                return {}
            elif len(possible_values) == 0:
                # it's possible to select no option in a drop-down list with
                # no options!
                return {}
            else:
                # most browsers pre-select the first value
                return {name: str(possible_values[0])}

        elif isinstance(widget, django.contrib.admin.widgets.RelatedFieldWidgetWrapper):
            subwidget = widget.widget
            subwidget.choices = list(widget.choices)
            return self.value_to_datadict(subwidget, name, value, strict)

        elif isinstance(widget, django.contrib.auth.forms.ReadOnlyPasswordHashWidget):
            return {}

        elif isinstance(widget, django.forms.widgets.Textarea):
            if value is None:
                value = ''
            return {name: force_unicode(value)}

        elif getattr(widget, '_format_value', None):
            if value is None:
                value = ''
            else:
                value = widget._format_value(value)
            return {name: force_unicode(value)}

        else:
            raise Exception("Don't know how to convert data to form values " +
                "for %s" % widget)

    def update_form_values(self, form, **new_values):
        """
        Extract the values from a form, change the ones passed as
        keyword arguments, empty keys whose value is None, delete keys
        which represent a file upload where no file is provided, and
        return a values dict suitable for self.client.post().
        """

        params = dict()

        field_names = [bound_field.name for bound_field in form]
        for name in new_values:
            if name not in field_names:
                self.fail("Tried to change value for unknown field %s. Valid "
                    "field names are: %s" % (name, field_names))

        from django.forms.widgets import MultiWidget
        for bound_field in form:
            # fields[k] returns a BoundField, not a django.forms.fields.Field
            # which is where the widget lives
            form_field = bound_field.field
            widget = form_field.widget

            # defaults to the current value bound into the form:
            value = new_values.get(bound_field.name, bound_field.value())

            # be strict with values passed by tests to this function,
            # and lax with values that were already in the record/form
            if form.prefix:
                param_name = "%s-%s" % (form.prefix, bound_field.name)
            else:
                param_name = bound_field.name

            new_params = self.value_to_datadict(widget, param_name, value,
                strict=(bound_field.name in new_values))

            params.update(new_params)

        return params

    def generate_dummy_data(self, form, bound_field, param_name,
            fields_to_delete):

        widget = bound_field.field.widget

        if isinstance(widget, HiddenInput):
            # hidden fields are not modifiable, so we should give them
            # their initial value

            value = bound_field.value()
            if getattr(widget, '_format_value', None):
                value = widget._format_value(value)
                if value is None:
                    value = ''

            return {param_name: str(value)}

        if not bound_field.field.required:
            return {}

        if (hasattr(bound_field.field, 'choices') or
                isinstance(widget, django.forms.widgets.Select)):

            choices = (
                getattr(bound_field.field, 'choices', None) or
                list(widget.choices)
            )

            possible_values = self.get_possible_values(choices)

            # Skip any blank first item, as it's usually not a valid choice.
            if possible_values[0] == '' and len(possible_values) >= 2:
                chosen_value = possible_values[1]
            else:
                chosen_value = possible_values[0]

            if isinstance(widget, django.forms.widgets.SelectMultiple):
                value = [str(chosen_value)]
            else:
                value = str(chosen_value)

        elif isinstance(bound_field.field, django.forms.fields.EmailField):
            value = "whee@example.com"

        elif isinstance(bound_field.field, django.forms.fields.DateField):
            value = str(datetime.date.today())

        elif isinstance(bound_field.field, django.forms.fields.FileField):
            value = ContentFile("Whee")
            value.name = "whee"

        elif isinstance(widget, ReCaptcha):
            fields_to_delete.append(bound_field.name)
            return {}

        elif isinstance(bound_field.field, django.forms.fields.IntegerField):
            value = "123"

        else:
            value = "Whee"

        return {param_name: value}

    def fill_form_with_dummy_data(self, form, post_data=None, create_new_form=True):
        import django.forms.fields
        import django.forms.widgets

        if post_data is None:
            post_data = {}
        else:
            post_data = dict(post_data)

        fields_to_delete = []

        for bound_field in form:
            if form.prefix:
                param_name = "%s-%s" % (form.prefix, bound_field.name)
            else:
                param_name = bound_field.name

            if param_name not in post_data:
                post_data.update(self.generate_dummy_data(form, bound_field,
                    param_name, fields_to_delete))

        query_dict = QueryDict('', mutable=True).copy()
        for key, value in post_data.iteritems():
            if hasattr(value, '__iter__'):
                query_dict.setlist(key, value)
            else:
                query_dict.setlist(key, [value])
        query_dict._mutable = False

        if create_new_form:
            new_form = form.__class__(query_dict)

            for field_name in fields_to_delete:
                del new_form.fields[field_name]

            # post_data is not very useful if fields_to_delete is not empty,
            # because any form constructed with it won't validate, but it is
            # useful under some circumstances, so return it anyway.
            """
            if fields_to_delete:
                post_data = None
            """

            return new_form, post_data
        else:
            return post_data
