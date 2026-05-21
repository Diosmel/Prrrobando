import asyncio
import base64
import logging

from backend.blocks.llm import AICredentials, AICredentialsField, LlmModel
from backend.sdk import (
    APIKeyCredentials,
    Block,
    BlockCategory,
    BlockOutput,
    BlockSchemaInput,
    BlockSchemaOutput,
    SchemaField,
)

from .helpers import DOWNLOADS_DIR, SESSIONS_DIR, build_llm, chromium_executable, ensure_browser_dirs

logger = logging.getLogger(__name__)


class BrowserUseAgentBlock(Block):
    """
    Agente de navegador IA tipo Manus.
    Navega, hace login, rellena formularios, extrae datos y descarga archivos.
    Usa Chromium local — completamente gratis, sin Browserbase.
    """

    class Input(BlockSchemaInput):
        task: str = SchemaField(
            description=(
                "Tarea en lenguaje natural. Usa {clave} para referenciar credenciales.\n\n"
                "Ejemplos:\n"
                "• 'Ve a amazon.es, busca auriculares gaming bajo 50€ y dame los 3 más baratos'\n"
                "• 'Entra a gmail.com con {username} y {password}, dame los 5 últimos correos no leídos'\n"
                "• 'Ve a linkedin.com, busca ofertas Python en Madrid, extrae títulos y empresas'\n"
                "• 'Rellena el formulario de contacto en la URL indicada con nombre=Juan García email=juan@test.com'"
            ),
        )
        starting_url: str = SchemaField(
            description="URL de inicio opcional. Si se deja vacío el agente decide adónde ir.",
            default="",
        )
        model: LlmModel = SchemaField(
            title="Modelo IA",
            default=LlmModel.CLAUDE_4_6_SONNET,
            description="Modelo de IA. Claude Sonnet o GPT-4.1 dan los mejores resultados.",
        )
        model_credentials: AICredentials = AICredentialsField()
        sensitive_data: dict[str, str] = SchemaField(
            description=(
                "Credenciales privadas referenciadas en la tarea con {clave}.\n"
                "Ej: {\"username\": \"tu@email.com\", \"password\": \"tupass\"}"
            ),
            default_factory=dict,
        )
        session_name: str = SchemaField(
            description=(
                "Nombre de sesión persistente. El mismo nombre mantiene cookies y login "
                "entre ejecuciones. Ej: 'gmail', 'amazon'. Vacío = sesión nueva."
            ),
            default="",
        )
        headless: bool = SchemaField(
            description="False = ver el navegador en pantalla. True = invisible (para servidores).",
            default=True,
        )
        max_steps: int = SchemaField(
            description="Pasos máximos. Aumentar para tareas largas o con muchas páginas.",
            default=100,
            advanced=True,
        )
        use_vision: bool = SchemaField(
            description="Activar visión (el agente analiza capturas de pantalla). Muy recomendado.",
            default=True,
            advanced=True,
        )
        max_actions_per_step: int = SchemaField(
            description="Acciones máximas por paso de razonamiento.",
            default=10,
            advanced=True,
        )

    class Output(BlockSchemaOutput):
        result: str = SchemaField(description="Resultado final de la tarea.")
        final_url: str = SchemaField(description="URL donde terminó el agente.")
        steps_taken: int = SchemaField(description="Número de pasos ejecutados.")
        urls_visited: list[str] = SchemaField(description="Todas las URLs visitadas durante la tarea.")
        final_screenshot: str = SchemaField(
            description=(
                "Captura de pantalla final en base64. "
                "Para verla: pega 'data:image/png;base64,<valor>' en el navegador."
            ),
        )
        errors: str = SchemaField(description="Errores encontrados, si los hubo.")

    def __init__(self):
        super().__init__(
            id="834c3aab-ee0d-4f2d-8937-b9f9cd9fa8bc",
            description=(
                "Agente de navegador IA tipo Manus — busca URLs, hace login, rellena formularios, "
                "extrae datos y descarga archivos. Gratis: usa Chromium local sin Browserbase."
            ),
            categories={BlockCategory.AI, BlockCategory.DEVELOPER_TOOLS},
            input_schema=BrowserUseAgentBlock.Input,
            output_schema=BrowserUseAgentBlock.Output,
        )

    async def run(
        self,
        input_data: Input,
        *,
        model_credentials: APIKeyCredentials,
        **kwargs,
    ) -> BlockOutput:
        from browser_use import Agent
        from browser_use.browser.browser import Browser, BrowserConfig
        from browser_use.browser.context import BrowserContextConfig

        ensure_browser_dirs()

        llm = build_llm(
            model_credentials.provider,
            input_data.model.value,
            model_credentials.api_key.get_secret_value(),
        )

        session_dir = (
            str(SESSIONS_DIR / input_data.session_name) if input_data.session_name else None
        )
        exe = chromium_executable()

        context_config = BrowserContextConfig(
            user_data_dir=session_dir,
            save_downloads_path=str(DOWNLOADS_DIR),
        )
        browser_config = BrowserConfig(
            headless=input_data.headless,
            new_context_config=context_config,
            **({"chrome_instance_path": exe} if exe else {}),
        )
        browser = Browser(config=browser_config)

        task = input_data.task
        if input_data.starting_url:
            task = f"Empieza navegando a {input_data.starting_url}. Luego: {task}"

        agent = Agent(
            task=task,
            llm=llm,
            browser=browser,
            sensitive_data=input_data.sensitive_data or None,
            use_vision=input_data.use_vision,
            max_actions_per_step=input_data.max_actions_per_step,
        )

        try:
            logger.info(f"BrowserUse: iniciando tarea (max_steps={input_data.max_steps})")
            history = await agent.run(max_steps=input_data.max_steps)

            result = history.final_result() or "Tarea completada."
            urls = history.urls()
            errors_list = [str(e) for e in (history.errors() or []) if e]

            final_screenshot = ""
            screenshots = history.screenshots() or []
            if screenshots:
                last = screenshots[-1]
                final_screenshot = (
                    base64.b64encode(last).decode() if isinstance(last, bytes) else str(last)
                )

            yield "result", result
            yield "final_url", urls[-1] if urls else ""
            yield "steps_taken", len(history.history)
            yield "urls_visited", urls
            yield "final_screenshot", final_screenshot
            yield "errors", "; ".join(errors_list)
        finally:
            await browser.close()


class BrowserUseScreenshotBlock(Block):
    """Captura una captura de pantalla completa de cualquier URL."""

    class Input(BlockSchemaInput):
        url: str = SchemaField(description="URL de la página a capturar.")
        wait_seconds: float = SchemaField(
            description="Segundos a esperar tras la carga antes de capturar.",
            default=2.0,
        )
        full_page: bool = SchemaField(
            description="True = página completa (incluyendo scroll). False = solo lo visible.",
            default=True,
        )
        headless: bool = SchemaField(default=True, advanced=True)

    class Output(BlockSchemaOutput):
        screenshot_base64: str = SchemaField(
            description="Imagen PNG en base64. Ver en navegador: data:image/png;base64,{valor}"
        )
        page_title: str = SchemaField(description="Título de la página capturada.")
        page_url: str = SchemaField(description="URL final (tras posibles redirecciones).")

    def __init__(self):
        super().__init__(
            id="6c5eb911-52bc-44d5-a972-2485f173286c",
            description="Captura de pantalla completa de cualquier página web.",
            categories={BlockCategory.AI, BlockCategory.DEVELOPER_TOOLS},
            input_schema=BrowserUseScreenshotBlock.Input,
            output_schema=BrowserUseScreenshotBlock.Output,
        )

    async def run(self, input_data: Input, **kwargs) -> BlockOutput:
        from playwright.async_api import async_playwright

        exe = chromium_executable()
        launch_kwargs = {"headless": input_data.headless}
        if exe:
            launch_kwargs["executable_path"] = exe

        async with async_playwright() as p:
            browser = await p.chromium.launch(**launch_kwargs)
            try:
                page = await browser.new_page()
                await page.goto(input_data.url, wait_until="networkidle", timeout=30000)
                if input_data.wait_seconds > 0:
                    await asyncio.sleep(input_data.wait_seconds)
                title = await page.title()
                final_url = page.url
                screenshot_bytes = await page.screenshot(full_page=input_data.full_page)
                yield "screenshot_base64", base64.b64encode(screenshot_bytes).decode()
                yield "page_title", title
                yield "page_url", final_url
            finally:
                await browser.close()


class BrowserUseDataExtractBlock(Block):
    """
    Extrae datos estructurados de cualquier página web usando IA.
    Scraping inteligente sin necesidad de conocer HTML ni XPath.
    """

    class Input(BlockSchemaInput):
        url: str = SchemaField(description="URL de donde extraer los datos.")
        extraction_goal: str = SchemaField(
            description=(
                "Qué datos extraer, en lenguaje natural.\n"
                "Ej: 'Extrae todos los títulos y precios de los productos' o "
                "'Dame el nombre, empresa y fecha de cada artículo de la página'"
            ),
        )
        output_format: str = SchemaField(
            description="Formato de salida: 'json', 'markdown', 'texto'.",
            default="json",
        )
        model: LlmModel = SchemaField(
            title="Modelo IA",
            default=LlmModel.CLAUDE_4_6_SONNET,
        )
        model_credentials: AICredentials = AICredentialsField()
        headless: bool = SchemaField(default=True, advanced=True)
        max_steps: int = SchemaField(default=30, advanced=True)

    class Output(BlockSchemaOutput):
        extracted_data: str = SchemaField(
            description="Datos extraídos en el formato solicitado (JSON, Markdown o texto)."
        )
        final_url: str = SchemaField(description="URL final tras posibles redirecciones.")

    def __init__(self):
        super().__init__(
            id="0c2cee45-d9d4-4038-bc4d-51cf86644a48",
            description=(
                "Extrae datos estructurados de páginas web con IA. "
                "Sin HTML ni XPath — solo describe qué quieres en lenguaje natural."
            ),
            categories={BlockCategory.AI, BlockCategory.DEVELOPER_TOOLS},
            input_schema=BrowserUseDataExtractBlock.Input,
            output_schema=BrowserUseDataExtractBlock.Output,
        )

    async def run(
        self,
        input_data: Input,
        *,
        model_credentials: APIKeyCredentials,
        **kwargs,
    ) -> BlockOutput:
        from browser_use import Agent
        from browser_use.browser.browser import Browser, BrowserConfig

        llm = build_llm(
            model_credentials.provider,
            input_data.model.value,
            model_credentials.api_key.get_secret_value(),
        )
        exe = chromium_executable()
        browser = Browser(
            config=BrowserConfig(
                headless=input_data.headless,
                **({"chrome_instance_path": exe} if exe else {}),
            )
        )
        task = (
            f"Ve a {input_data.url} y extrae en formato {input_data.output_format}: "
            f"{input_data.extraction_goal}. "
            f"Devuelve ÚNICAMENTE los datos extraídos, sin explicaciones adicionales."
        )
        agent = Agent(task=task, llm=llm, browser=browser, use_vision=True)
        try:
            history = await agent.run(max_steps=input_data.max_steps)
            urls = history.urls()
            yield "extracted_data", history.final_result() or "{}"
            yield "final_url", urls[-1] if urls else input_data.url
        finally:
            await browser.close()
