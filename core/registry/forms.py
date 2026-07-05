from django import forms
from django.utils.translation import gettext_lazy as _


class RegistryImportForm(forms.Form):
    registry_file = forms.FileField(
        label=_("Registry file"),
        help_text=_("Upload the state registry spreadsheet in .xlsx or .ods format. The import will be queued."),
    )

    def clean_registry_file(self):
        registry_file = self.cleaned_data["registry_file"]
        if not registry_file.name.lower().endswith((".xlsx", ".ods")):
            raise forms.ValidationError(_("Upload an .xlsx or .ods registry file."))
        return registry_file
