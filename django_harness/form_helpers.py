from calendar import month_abbr, monthrange
from datetime import date
from dateutil.relativedelta import relativedelta
from django import forms


def year_range(start_year, end_year, allow_blank=True):
    years_range = [(year, str(year)) for year in range(start_year, end_year+1)]
    if allow_blank:
        new_years_range = [(0, '--')]
        new_years_range.extend(years_range)
        years_range = new_years_range
    return years_range


def year_range_relative_year(years_back=10, years_forward=2, allow_blank=True):
    year = date.today().year
    return year_range(year - years_back, year + years_forward, allow_blank)


def year_range_from_date_to_now(from_date, allow_blank=True):
    this_year = date.today().year
    return year_range(from_date.year, this_year, allow_blank)


def month_range():
    return [(i, name) for i, name in enumerate(month_abbr)]


def clean_month_year_helper(cleaned_data, prefix, start_or_end):
    year = cleaned_data.get(prefix + 'year')
    month = cleaned_data.get(prefix + 'month')
    if year:
        year = int(year)
    if month:
        month = int(month)
    if month and not year:
        raise forms.ValidationError("Cannot select month without corresponding year")
    if year:
        if month:
            if start_or_end == 'start':
                return date(year=year, month=month, day=1)
            else:
                num, last_day_of_month = monthrange(year, month)
                return date(year=year, month=month, day=last_day_of_month)
        else:
            if start_or_end == 'start':
                return date(year=year, month=1, day=1)
            else:
                return date(year=year, month=12, day=31)


def last_month_ago_to_today_query_string():
    today = date.today()
    last_month = today - relativedelta(months=1)
    return "after_month=%d&after_year=%d&before_month=%d&before_year=%d" % \
        (last_month.month, last_month.year, today.month, today.year)
