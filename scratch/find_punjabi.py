import asyncio
import edge_tts

async def find_punjabi():
    voices = await edge_tts.VoicesManager.create()
    for v in voices.voices:
        if "pa-" in v['Locale'] or "Punjabi" in v['FriendlyName']:
            print(f"Locale: {v['Locale']}, ShortName: {v['ShortName']}, Gender: {v['Gender']}")

if __name__ == "__main__":
    asyncio.run(find_punjabi())
