# league/forms.py
from django import forms
from .models import Bet, OVER_UNDER_CHOICES

class BetSimpleForm(forms.ModelForm):
    # Over/Under as a dropdown; only shown/required for TOTAL/PROP
    over_under = forms.ChoiceField(
        choices=[("", "Select…")] + list(OVER_UNDER_CHOICES),
        widget=forms.Select,
        required=False,
        label="Over/Under"
    )

    class Meta:
        model = Bet
        fields = ["pick_text", "line", "american_odds", "parlay_selected", "over_under"]
        widgets = {
            # Mobile decimal keypad; allow +/− and a dot via pattern
            "line": forms.TextInput(attrs={
                "inputmode": "decimal",
                "pattern": r"[+-]?\d*\.?\d*",
                "placeholder": "-3.5 or 47.5",
                "autocomplete": "off",
            }),
            # Mobile numeric keypad; allow optional leading +/− via pattern
            "american_odds": forms.TextInput(attrs={
                "inputmode": "numeric",
                "pattern": r"[+-]?\d*",
                "placeholder": "+110 or -120",
                "autocomplete": "off",
            }),
            "pick_text": forms.TextInput(attrs={
                "autocomplete": "off",
                "placeholder": "e.g., KC -3.5 @ LAC",
            }),
        }

    def __init__(self, *args, **kwargs):
        # accept bet_type from the view so we can show/hide Over/Under
        self.bet_type = kwargs.pop("bet_type", "SPREAD")
        super().__init__(*args, **kwargs)

        if self.bet_type in ("TOTAL", "PROP"):
            self.fields["over_under"].required = True
        else:
            # SPREAD: remove O/U entirely (not shown, not posted)
            self.fields.pop("over_under", None)

    def clean(self):
        cleaned = super().clean()
        if self.bet_type == "SPREAD":
            cleaned["over_under"] = None
        else:
            if not cleaned.get("over_under"):
                self.add_error("over_under", "Select Over or Under.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.bet_type == "SPREAD":
            obj.over_under = None
        if commit:
            obj.save()
        return obj