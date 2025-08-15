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
            "line": forms.TextInput(attrs={
                "inputmode": "decimal",
                "pattern": r"[+-]?\d*\.?\d*",
                "placeholder": "-3.5 or 47.5",
                "autocomplete": "off",
            }),
            "american_odds": forms.TextInput(attrs={
                "inputmode": "numeric",
                "pattern": r"[+-]?\d*",
                "placeholder": "+110 or -120",
                "autocomplete": "off",
            }),
            "pick_text": forms.TextInput(attrs={
                "autocomplete": "off",
                # will be overridden per bet_type below
                "placeholder": "e.g., KC -3.5 @ LAC",
            }),
        }

    def __init__(self, *args, **kwargs):
        # accept bet_type from the view; if not provided, infer from the form prefix
        passed_bt = kwargs.pop("bet_type", None)
        super().__init__(*args, **kwargs)
        self.bet_type = passed_bt or (self.prefix if self.prefix in ("SPREAD", "TOTAL", "PROP") else "SPREAD")

        # Set pick_text placeholder per bet type
        placeholders = {
            "SPREAD": "e.g., Cardinals",
            "TOTAL": "e.g., Eagles/Cowboys",
            "PROP": "e.g., Drake Maye Passing Yds",
        }
        self.fields["pick_text"].widget.attrs["placeholder"] = placeholders.get(self.bet_type, "Enter pick")

        # Show/hide Over/Under
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
