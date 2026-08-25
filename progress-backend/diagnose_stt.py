"""Send one recording to Deepgram twice - as Russian, then as English.

Bypasses the app entirely, so it answers one question cleanly: does Deepgram transcribe
your Russian correctly when told the language is Russian? If it does, the problem is in
how the app passes the language. If it does not, the problem is the model.

Run from progress-backend, with the venv active:

    python diagnose_stt.py                  # uses the newest file in data/audio
    python diagnose_stt.py path\\to\\file.webm
"""

import sys
from pathlib import Path

import httpx

from app.config import settings

MIME = {
    ".webm": "audio/webm",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".ogg": "audio/ogg",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
}


def newest_recording() -> Path:
    root = Path(settings.audio_dir)
    files = [f for f in root.rglob("*") if f.is_file() and f.suffix in MIME]
    if not files:
        raise SystemExit(f"No audio found under {root.resolve()}. Record a check-in first.")
    return max(files, key=lambda f: f.stat().st_mtime)


def transcribe(path: Path, model: str, language: str | None, keyterms: bool) -> None:
    params: dict[str, object] = {
        "model": model,
        "smart_format": "true",
        "punctuate": "true",
    }
    if language:
        params["language"] = language
    else:
        params["detect_language"] = "true"
    if keyterms and model.startswith("nova-3") and language != "multi":
        params["keyterm"] = settings.keyterm_list

    label = f"{model} / language={language or 'auto-detect'}"
    try:
        resp = httpx.post(
            f"{settings.deepgram_base_url}/v1/listen",
            params=params,
            headers={
                "Authorization": f"Token {settings.deepgram_api_key}",
                "Content-Type": MIME.get(path.suffix, "application/octet-stream"),
            },
            content=path.read_bytes(),
            timeout=120,
        )
    except httpx.HTTPError as exc:
        print(f"  {label:38} NETWORK ERROR: {exc}")
        return

    if resp.status_code >= 400:
        print(f"  {label:38} HTTP {resp.status_code}: {resp.text[:160]}")
        return

    body = resp.json()
    channel = body["results"]["channels"][0]
    text = (channel["alternatives"][0].get("transcript") or "").strip()
    detected = channel.get("detected_language", "")
    duration = body.get("metadata", {}).get("duration")
    suffix = f"  [detected: {detected}]" if detected else ""
    print(f"  {label:38} {duration:.1f}s{suffix}")
    print(f"    -> {text or '(empty)'}")


def main() -> None:
    if not settings.deepgram_api_key:
        raise SystemExit("DEEPGRAM_API_KEY is not set in .env")

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else newest_recording()
    if not path.exists():
        raise SystemExit(f"No such file: {path}")

    size_kb = path.stat().st_size / 1024
    print(f"\nFile: {path}  ({size_kb:.0f} KB)")
    print(f"Configured: STT_LANGUAGE={settings.stt_language!r} "
          f"DEEPGRAM_MODEL={settings.deepgram_model!r}\n")

    for model, language, keyterms in [
        ("nova-3", None, False),   # detection alone - what the app now does
        ("nova-3", None, True),    # detection + English keyterms - what broke it
        ("nova-3", "ru", True),
        ("nova-3", "multi", False),
        ("nova-2", "ru", False),
    ]:
        transcribe(path, model, language, keyterms)
        print()

    print("Compare the first two lines. They differ only in whether English keyterms")
    print("were sent alongside language detection. If the second is English nonsense,")
    print("that is the bug: keyterms bias detection and must only be used with a")
    print("pinned language.\n")


if __name__ == "__main__":
    main()
