from __future__ import unicode_literals, absolute_import

from datetime import date, datetime, timedelta
from django.utils.timezone import now

class DateUtilsMixin(object):
    def from_today(self, **kwargs):
        return date.today() + timedelta(**kwargs)

    def from_now(self, **kwargs):
        naive = kwargs.pop('naive', False)
        remove_ms = kwargs.pop('remove_ms', False)
        time_now = datetime.now() if naive else now()
        time_then = time_now + timedelta(**kwargs)
        if remove_ms:
            time_then -= timedelta(microseconds=time_then.microsecond)
        return time_then

    def format_date(self, date, date_format=None):
        from django.template.defaultfilters import date as format_date
        return format_date(date, date_format)

