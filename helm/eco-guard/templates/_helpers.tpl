{{- define "eco-guard.fullname" -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "eco-guard.labels" -}}
app.kubernetes.io/name: eco-guard
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion }}
app.kubernetes.io/managed-by: helm
{{- end }}

{{- define "eco-guard.selectorLabels" -}}
app.kubernetes.io/name: eco-guard
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
