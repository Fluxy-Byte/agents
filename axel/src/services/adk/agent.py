import os

from google.adk.agents import Agent

root_agent = Agent(
    name="axel",
    model=os.getenv("GOOGLE_ADK_MODEL", "gemini-2.5-flash"),
    description="Agente Axel.",
    instruction=(
        "Você é o Axel, assistente de atendimento via WhatsApp. "
        "Responda de forma objetiva, cordial e profissional."
    ),
)
