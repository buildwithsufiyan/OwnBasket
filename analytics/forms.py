from datetime import datetime, time, timedelta

from django import forms
from django.utils import timezone


class DateRangeForm(forms.Form):
    PRESETS = (
        ('today', 'Today'), ('yesterday', 'Yesterday'), ('last_7_days', 'Last 7 days'),
        ('last_30_days', 'Last 30 days'), ('this_month', 'This month'),
        ('previous_month', 'Previous month'), ('this_year', 'This year'), ('custom', 'Custom range'),
    )
    preset = forms.ChoiceField(choices=PRESETS, required=False, initial='last_30_days')
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    def clean(self):
        cleaned = super().clean()
        today = timezone.localdate()
        preset = cleaned.get('preset') or 'last_30_days'
        start, end = self._preset_dates(preset, today)
        if preset == 'custom':
            start, end = cleaned.get('start_date'), cleaned.get('end_date')
            if not start or not end:
                raise forms.ValidationError('Start and end dates are required for a custom range.')
        if start > end:
            raise forms.ValidationError('Start date cannot be after end date.')
        if end > today:
            raise forms.ValidationError('Future dates are not available in historical reports.')
        if (end - start).days > 3660:
            raise forms.ValidationError('Date range cannot exceed ten years.')
        tz = timezone.get_current_timezone()
        cleaned['start'] = timezone.make_aware(datetime.combine(start, time.min), tz)
        cleaned['end'] = timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min), tz)
        cleaned['resolved_start_date'] = start
        cleaned['resolved_end_date'] = end
        return cleaned

    @staticmethod
    def _preset_dates(preset, today):
        if preset == 'today':
            return today, today
        if preset == 'yesterday':
            day = today - timedelta(days=1)
            return day, day
        if preset == 'last_7_days':
            return today - timedelta(days=6), today
        if preset == 'this_month':
            return today.replace(day=1), today
        if preset == 'previous_month':
            last = today.replace(day=1) - timedelta(days=1)
            return last.replace(day=1), last
        if preset == 'this_year':
            return today.replace(month=1, day=1), today
        return today - timedelta(days=29), today


def validated_period(params):
    form = DateRangeForm(params or {'preset': 'last_30_days'})
    if not form.is_valid():
        return form, None
    return form, (form.cleaned_data['start'], form.cleaned_data['end'])
