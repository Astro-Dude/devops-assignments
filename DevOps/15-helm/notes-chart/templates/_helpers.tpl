{{/*
Helpers keep repeated logic in one place. Anything defined here is available to
every template in the chart via `include`.
*/}}

{{/* A full name for resources: <release>-<chart>, truncated to the 63-char DNS limit */}}
{{- define "notes-app.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* The labels every object in this chart should carry */}}
{{- define "notes-app.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
environment: {{ .Values.config.environment }}
{{- end -}}

{{/* The subset of labels used for matching. These must NEVER change between
     upgrades - a Deployment's selector is immutable. */}}
{{- define "notes-app.selectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
