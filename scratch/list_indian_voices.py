import asyncio
import edge_tts

async def list_indian_voices():
    voices = await edge_tts.VoicesManager.create()
    for voice in voices.voices:
        if "-IN" in voice['Locale']:
            print(f"Locale: {voice['Locale']}, ShortName: {voice['ShortName']}, Gender: {voice['Gender']}")

if __name__ == "__main__":
    asyncio.run(list_indian_voices())
