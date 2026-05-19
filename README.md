# IA Open Source Starter para Diosmel

Este repositorio queda preparado para trabajar con una inteligencia artificial open source adaptable.

## Opción recomendada: Open WebUI

Open WebUI es una interfaz tipo ChatGPT, self-hosted, compatible con Ollama y APIs compatibles con OpenAI. Sirve para crear tu propio chat de IA, cambiar diseño, agregar funciones y conectarlo con modelos locales o externos.

Repositorio original:

```bash
git clone https://github.com/open-webui/open-webui.git
```

## Instalación rápida con Docker

```bash
docker run -d \
  -p 3000:8080 \
  -v open-webui:/app/backend/data \
  --name open-webui \
  --restart always \
  ghcr.io/open-webui/open-webui:main
```

Luego abre:

```text
http://localhost:3000
```

## Instalación usando Ollama local

Primero instala Ollama y descarga un modelo:

```bash
ollama pull llama3.2
```

Luego ejecuta Open WebUI conectado a Ollama:

```bash
docker run -d \
  -p 3000:8080 \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  -v open-webui:/app/backend/data \
  --name open-webui \
  --restart always \
  ghcr.io/open-webui/open-webui:main
```

## Cómo traer el código completo dentro de este repo

Si quieres convertir este repo en una copia editable del proyecto completo:

```bash
git clone https://github.com/open-webui/open-webui.git temp-open-webui
cp -r temp-open-webui/* .
cp -r temp-open-webui/.[!.]* . 2>/dev/null || true
rm -rf temp-open-webui

git add .
git commit -m "Import Open WebUI base project"
git push
```

## Para qué sirve este repo ahora

- Guardar notas de adaptación.
- Probar cambios de diseño.
- Preparar una versión personalizada.
- Documentar qué archivos tocar.
- Convertirlo luego en una copia completa de Open WebUI.

## Próximos cambios recomendados

1. Cambiar nombre, logo y colores.
2. Configurar proveedor de IA: Ollama, OpenAI, Gemini u otro compatible.
3. Agregar una página de login personalizada.
4. Crear un sistema de herramientas propias.
5. Preparar deploy en servidor o VPS.
