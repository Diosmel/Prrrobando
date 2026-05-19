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

logger = logging.getLogger(__name__)


class BrowserUseBlock(Block):
    """
    Controla un navegador local (Chrome/Chromium) usando IA para automatizar
    tareas web. Alternativa gratuita a Browserbase/Stagehand.

    Requisito: ejecutar `playwright install chromium` tras instalar dependencias.
    """

    class Input(BlockSchemaInput):
        task: str = SchemaField(
            description=(
                "Descripción en lenguaje natural de lo que debe hacer el agente. "
                "Usa {clave} para referenciar datos sensibles. "
                "Ejemplo: 'Ve a gmail.com, inicia sesión con {username} y {password} "
                "y dame los últimos 5 correos no leídos.'"
            ),
        )
        model: LlmModel = SchemaField(
            title="Modelo IA",
            description="Modelo de IA que actúa como cerebro del agente de navegador.",
            default=LlmModel.CLAUDE_4_6_SONNET,
        )
        model_credentials: AICredentials = AICredentialsField()
        sensitive_data: dict[str, str] = SchemaField(
            description=(
                "Credenciales y datos sensibles referenciados en la tarea con {clave}. "
                "Ejemplo: {'username': 'tu@email.com', 'password': 'tucontraseña'}"
            ),
            default_factory=dict,
        )
        headless: bool = SchemaField(
            description=(
                "True: navegador invisible (para servidores). "
                "False: ver el navegador en pantalla mientras trabaja."
            ),
            default=False,
            advanced=True,
        )
        max_steps: int = SchemaField(
            description="Número máximo de pasos que puede dar el agente antes de parar.",
            default=50,
            advanced=True,
        )

    class Output(BlockSchemaOutput):
        result: str = SchemaField(
            description="Resultado final de la tarea ejecutada por el agente."
        )
        final_url: str = SchemaField(
            description="URL en la que estaba el navegador al terminar la tarea."
        )

    def __init__(self):
        super().__init__(
            id="834c3aab-ee0d-4f2d-8937-b9f9cd9fa8bc",
            description=(
                "Controla tu navegador local con IA para automatizar tareas web: "
                "buscar URLs, iniciar sesión, rellenar formularios, hacer clicks y extraer datos. "
                "Gratis: usa Playwright (Chrome/Chromium local) en lugar de Browserbase."
            ),
            categories={BlockCategory.AI, BlockCategory.DEVELOPER_TOOLS},
            input_schema=BrowserUseBlock.Input,
            output_schema=BrowserUseBlock.Output,
        )

    async def run(
        self,
        input_data: Input,
        *,
        model_credentials: APIKeyCredentials,
        **kwargs,
    ) -> BlockOutput:
        # Lazy imports: dependencias pesadas opcionales
        from browser_use import Agent
        from browser_use.browser.browser import Browser, BrowserConfig

        api_key = model_credentials.api_key.get_secret_value()
        provider = model_credentials.provider
        model_name = input_data.model.value

        if provider == "anthropic":
            from langchain_anthropic import ChatAnthropic

            llm = ChatAnthropic(model=model_name, api_key=api_key)  # type: ignore[call-arg]
        elif provider == "openai":
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(model=model_name, api_key=api_key)  # type: ignore[call-arg]
        else:
            raise ValueError(
                f"Proveedor '{provider}' no soportado. Usa credenciales de Anthropic u OpenAI."
            )

        browser = Browser(config=BrowserConfig(headless=input_data.headless))

        agent = Agent(
            task=input_data.task,
            llm=llm,
            browser=browser,
            sensitive_data=input_data.sensitive_data or None,
        )

        try:
            logger.info("BrowserUse: iniciando agente para tarea: %s", input_data.task[:80])
            history = await agent.run(max_steps=input_data.max_steps)

            result = history.final_result() or "Tarea completada sin resultado de texto."
            visited_urls = history.urls()
            final_url = visited_urls[-1] if visited_urls else ""

            yield "result", result
            yield "final_url", final_url
        finally:
            await browser.close()
