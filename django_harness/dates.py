from __future__ import unicode_literals, absolute_import

from datetime import date, timedelta

class DateUtilsMixin(object):
    def from_today(self, **kwargs):
        return date.today() + timedelta(**kwargs)

    def format_date(self, date):
        from django.template.defaultfilters import date as format_date
        return format_date(date)

