# MiMo V2.5 TTS API Research

## Sources

- Xiaomi model page: `https://mimo.xiaomi.com/mimo-v2-5-tts/`
- Xiaomi official Skill repository: `https://github.com/XiaomiMiMo/MiMo-Skills`
- Contract source: `skills/mimo-v2-5-tts/scripts/mimo_tts.py`

## Confirmed Contract

The official script uses the OpenAI Python client with:

```python
OpenAI(api_key=api_key, base_url="https://api.xiaomimimo.com/v1")

client.chat.completions.create(
    model="mimo-v2.5-tts",
    messages=[{"role": "assistant", "content": text}],
    audio={"format": "wav", "voice": voice},
)
```

The response audio is Base64-encoded at `completion.choices[0].message.audio.data`.
Natural-language delivery instructions are sent as a preceding `user` message. This is the only
documented way to express speed for MiMo, so the application maps its numeric speed setting to a
short instruction instead of sending an undocumented numeric audio field.

## Preset Voices

- Chinese: `冰糖`, `茉莉`, `苏打`, `白桦`
- English: `Mia`, `Chloe`, `Milo`, `Dean`

The base model requires a voice. Voice design and voice clone use different request shapes and are
outside this task.

## Length Guidance

The official Skill recommends a single request for most inputs and sentence/paragraph splitting only
after 2500 Chinese characters. MoFeng will enforce 2500 characters per backend request and perform
ordered splitting in the frontend so browser speech and model speech share one playback queue.

## Integration Consequences

- MiMo is not implemented through `/v1/audio/speech`.
- The provider `base_url` remains user-configurable; users should save the API version prefix (for
  Xiaomi, `https://api.xiaomimimo.com/v1`).
- MiMo returns JSON with Base64 WAV; OpenAI Speech-compatible providers return binary audio.
- Logs and client errors must not contain the API key, source text, or upstream response body.
