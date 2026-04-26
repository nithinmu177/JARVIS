import asyncio
import edge_tts
import json

async def generate_map():
    voices = await edge_tts.VoicesManager.create()
    voice_map = {}
    
    # We want one good default voice per locale
    # Prefer Female for a JARVIS/Aura feel if possible, or just pick the first one
    locales = {}
    for v in voices.voices:
        locale = v['Locale']
        if locale not in locales:
            locales[locale] = v['ShortName']
        else:
            # Prefer 'Neural' and certain genders if available
            if 'Neural' in v['ShortName'] and (v['Gender'] == 'Female' or 'Neural' in v['ShortName']):
                # Simple heuristic to pick a "good" voice
                if 'Expressive' in v['ShortName'] or 'Multilingual' in v['ShortName']:
                    locales[locale] = v['ShortName']
    
    print(json.dumps(locales, indent=2))

if __name__ == "__main__":
    asyncio.run(generate_map())
