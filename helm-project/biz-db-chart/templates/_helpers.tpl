{{/* 通用标签辅助函数 */}}
{{- define "biz-db-chart.labels" -}}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/chart: {{ .Chart.Name }}
{{- end -}}
