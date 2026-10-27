{{ with get . "deeptutorHome" -}}
# DeepTutor runtime home shared by the CLI and Web app.
if [ -z "${DEEPTUTOR_HOME:-}" ]; then
    export DEEPTUTOR_HOME='{{ . | replace "'" "'\\''" }}'
fi
{{- end }}
