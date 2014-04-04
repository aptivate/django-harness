class FormUtilsMixin(object):
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
            possible_values = [v for v, label in choices]
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
            elif len(choices) == 0:
                # it's possible to select no option in a drop-down list with
                # no options!
                return {}
            else:
                # most browsers pre-select the first value
                return {name: str(choices[0][0])}

        elif isinstance(widget, django.contrib.admin.widgets.RelatedFieldWidgetWrapper):
            subwidget = widget.widget
            subwidget.choices = list(widget.choices)
            return self.value_to_datadict(subwidget, name, value, strict)

        elif isinstance(widget, django.forms.widgets.Textarea):
            return {name: force_unicode(value)}

        elif isinstance(widget, django.contrib.auth.forms.ReadOnlyPasswordHashWidget):
            return {}

        elif getattr(widget, '_format_value', None):
            value = widget._format_value(value)
            if value is None:
                value = ''
            return {name: value}

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
            new_params = self.value_to_datadict(widget, bound_field.name, value,
                strict=(bound_field.name in new_values))

            params.update(new_params)

        return params


