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

class FuturesForm(forms.Form):
    pick1_text = forms.CharField(label="Super Bowl Winner", max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "e.g., Patriots to win Super Bowl", "autocomplete": "off"}))
    pick1_odds = forms.IntegerField(label="Super Bowl Odds",
        widget=forms.TextInput(attrs={"placeholder": "+400", "autocomplete": "off", "inputmode": "text", "pattern": r"[+-]?\d+"}))

    pick2_text = forms.CharField(label="MVP Winner", max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "e.g., Drake Maye MVP", "autocomplete": "off"}))
    pick2_odds = forms.IntegerField(label="MVP Odds",
        widget=forms.TextInput(attrs={"placeholder": "+650", "autocomplete": "off", "inputmode": "text", "pattern": r"[+-]?\d+"}))

    pick3_text = forms.CharField(label="Team O/U", max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "e.g., Patriots over 8.5 wins", "autocomplete": "off"}))
    pick3_odds = forms.IntegerField(label="Odds",
        widget=forms.TextInput(attrs={"placeholder": "+105 or -115", "autocomplete": "off", "inputmode": "text", "pattern": r"[+-]?\d+"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            w = field.widget
            classes = w.attrs.get("class", "").split()

            def add(cls):
                if cls not in classes:
                    classes.append(cls)

            # Pick the right Bootstrap class per widget type
            from django import forms as djf
            if isinstance(w, djf.Select):
                add("form-select")
            elif isinstance(w, (djf.CheckboxInput, djf.RadioSelect)):
                add("form-check-input")
            else:
                add("form-control")

            w.attrs["class"] = " ".join(classes)

            # Optional: special-case a known checkbox field
            if name == "parlay_selected":
                w.attrs["class"] = "form-check-input"

    # Enforce valid American odds on all three
    def _clean_odds(self, val, label):
        try:
            v = int(str(val).strip().replace("+", ""))
        except Exception:
            raise forms.ValidationError(f"{label}: enter integer odds like -110 or +250.")
        if v == 0 or (-100 < v < 100):
            raise forms.ValidationError(f"{label}: American odds must be ≤ -101 or ≥ +100.")
        return v

    def clean(self):
        c = super().clean()
        if "pick1_odds" in c:
            c["pick1_odds"] = self._clean_odds(c["pick1_odds"], "Super Bowl Odds")
        if "pick2_odds" in c:
            c["pick2_odds"] = self._clean_odds(c["pick2_odds"], "MVP Odds")
        if "pick3_odds" in c:
            c["pick3_odds"] = self._clean_odds(c["pick3_odds"], "Odds")
        return c