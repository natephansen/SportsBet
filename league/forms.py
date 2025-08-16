# league/forms.py
from django import forms
from .models import Bet, OVER_UNDER_CHOICES

class BetSimpleForm(forms.ModelForm):
    over_under = forms.ChoiceField(
        choices=[("", "Select…")] + list(OVER_UNDER_CHOICES),
        widget=forms.Select, required=False, label="Over/Under"
    )

    class Meta:
        model = Bet
        fields = ["pick_text", "line", "american_odds", "parlay_selected", "over_under"]
        widgets = {
            "line": forms.TextInput(attrs={
                # show full keyboard on mobile so +/- are available
                "inputmode": "text",         # or simply remove this key
                "pattern": r"[+-]?\d*\.?\d*",  # still hint valid format
                "placeholder": "-3.5 or 47.5",
                "autocomplete": "off",
                "aria-label": "Line (e.g., -3.5 or 47.5)",
            }),
            "american_odds": forms.TextInput(attrs={
                # show full keyboard on mobile so +/- are available
                "inputmode": "text",         # or remove this key
                "pattern": r"[+-]?\d*",
                "placeholder": "+110 or -120",
                "autocomplete": "off",
                "aria-label": "American odds (e.g., +110 or -120)",
            }),
            "pick_text": forms.TextInput(attrs={
                "autocomplete": "off",
                "placeholder": "e.g., KC -3.5 @ LAC",
            }),
        }

    def __init__(self, *args, **kwargs):
        self.bet_type = kwargs.pop("bet_type", "SPREAD")
        super().__init__(*args, **kwargs)
        if self.bet_type in ("TOTAL", "PROP"):
            self.fields["over_under"].required = True
        else:
            self.fields.pop("over_under", None)