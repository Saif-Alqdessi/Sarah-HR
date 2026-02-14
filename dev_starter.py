#!/usr/bin/env python3
"""
Dev starter: runs ngrok, backend, and frontend. Ctrl+C kills all processes.
Updates Vapi assistant webhook URL with ngrok tunnel.
"""

import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
import urllib.error

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

processes = []


def load_env():
    """Load .env from root and backend into os.environ."""
    for path in [
        os.path.join(PROJECT_ROOT, ".env"),
        os.path.join(BACKEND_DIR, ".env"),
    ]:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        k, v = k.strip(), v.strip()
                        if v.startswith('"') and v.endswith('"'):
                            v = v[1:-1]
                        elif v.startswith("'") and v.endswith("'"):
                            v = v[1:-1]
                        os.environ.setdefault(k, v)


VAPI_SYSTEM_PROMPT = """بروتوكول المحادثة — أنتِ سارة، مسؤولة التوظيف في مخبز جولد كروست. هدفك محادثة طبيعية حوالي ٥ دقائق مع {{candidate_name}} لوظيفة {{target_role}}.

القاعدة ١: اطرحي سؤالاً واحداً فقط. ثم اصمتي تماماً وانتظري رد المرشح. لا تكملي ولا تسألي سؤالاً ثانياً قبل أن يرد.

القاعدة ٢: بعد ما يتكلم المرشح، ابدئي ردك برد فعل طبيعي (مثلاً: جميل جداً، فهمت عليك، ممتاز، تمام) ثم اسألي السؤال التالي. سؤال واحد فقط.

القاعدة ٣: لا تقولي أبداً "سأسألك أسئلة" أو "سأطرح عليك أسئلة". تكلمي كإنسانة طبيعية.

اللهجة: عربية فصحى مهذبة أو لهجة بيضاء احترافية (أردنية/شامية خفيفة). تجنبي التحول للمصرية أو للروبوتية."""


def update_vapi_webhook(ngrok_url: str, api_key: str, assistant_id: str) -> bool:
    """PATCH Vapi assistant with production-ready settings: stability, voice, model, call limits."""
    webhook_url = f"{ngrok_url}/api/vapi-webhook"
    payload = {
        "server": {"url": webhook_url},
        "maxDurationSeconds": 900,
        "silenceTimeoutSeconds": 45,
        "voice": {
            "provider": "11labs",
            "voiceId": "SAz9YHcvj6GT2YYYt9yo",
            "stability": 0.8,
            "similarityBoost": 0.8,
        },
        "transcriber": {"provider": "deepgram", "model": "nova-2", "language": "ar"},
        "firstMessage": "أهلاً بك {{candidate_name}}! أنا سارة من مخبز جولد كروست، كيف حالك اليوم؟",
        "model": {
            "provider": "openai",
            "model": "gpt-4o",
            "systemPrompt": VAPI_SYSTEM_PROMPT,
            "messages": [{"role": "system", "content": VAPI_SYSTEM_PROMPT}],
        },
    }
    print("PATCH payload: model=gpt-4o, voice=11labs/Layla (stability=0.8), maxDuration=900s, silenceTimeout=45s")
    req = urllib.request.Request(
        f"https://api.vapi.ai/assistant/{assistant_id}",
        data=json.dumps(payload).encode("utf-8"),
        method="PATCH",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode()
            print("--- Vapi PATCH response (full JSON) ---")
            try:
                parsed = json.loads(body)
                print(json.dumps(parsed, indent=2, ensure_ascii=False))
            except json.JSONDecodeError:
                print(body)
            print("--- end response ---")
            if 200 <= resp.getcode() < 300:
                print("Vapi PATCH: ACCEPTED. Assistant updated successfully.")
                print(f"Webhook URL: {webhook_url}")
                return True
            print("Vapi PATCH: REJECTED (non-2xx status). Check response above.")
            return False
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print("--- Vapi PATCH ERROR (status != 200) ---")
        print(f"Status: {e.code} {e.reason}")
        print("Full response body:")
        try:
            parsed = json.loads(body)
            print(json.dumps(parsed, indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            print(body)
        print("--- If you see 'Invalid Voice ID' or 'Unauthorized', check VAPI_API_KEY and ElevenLabs credentials. ---")
        return False
    except Exception as e:
        print(f"Vapi webhook update failed: {e}")
        return False


def kill_all():
    for p in processes:
        try:
            if sys.platform == "win32":
                p.terminate()
            else:
                os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass


def main():
    load_env()
    api_key = os.environ.get("VAPI_API_KEY")
    assistant_id = os.environ.get("VAPI_ASSISTANT_ID")

    def sig_handler(signum, frame):
        print("\nShutting down...")
        kill_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, sig_handler)

    print("Starting ngrok http 8001...")
    ngrok_cmd = "ngrok http 8001"
    kw = {"cwd": PROJECT_ROOT}
    if sys.platform == "win32":
        kw["shell"] = True
    else:
        kw["preexec_fn"] = os.setsid
    ngrok_proc = subprocess.Popen(ngrok_cmd, **kw)
    processes.append(ngrok_proc)

    ngrok_url = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=5) as resp:
                data = json.loads(resp.read().decode())
                tunnels = data.get("tunnels", [])
                for t in tunnels:
                    url = t.get("public_url")
                    if url and url.startswith("https://"):
                        ngrok_url = url
                        print("\n" + "=" * 60)
                        print("NGROK URL (copy to Vapi webhook):")
                        print(f"  {url}/api/vapi-webhook")
                        print("=" * 60 + "\n")
                        break
                if ngrok_url:
                    break
            if not ngrok_url and attempt == 4:
                print("Could not get ngrok URL. Check http://127.0.0.1:4040")
        except Exception as e:
            if attempt < 4:
                print(f"Waiting for ngrok... (attempt {attempt + 1}/5)")
                time.sleep(2)
            else:
                print(f"Could not fetch ngrok URL: {e}")

    if ngrok_url and (not api_key or not assistant_id):
        print("Skipping Vapi update: set VAPI_API_KEY and VAPI_ASSISTANT_ID in .env\n")

    print("Starting backend (FastAPI on port 8001)...")
    py = f'"{sys.executable}"' if " " in sys.executable else sys.executable
    backend_cmd = f"{py} -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload"
    backend_proc = subprocess.Popen(
        backend_cmd,
        cwd=BACKEND_DIR,
        shell=True,
    )
    processes.append(backend_proc)

    time.sleep(1)

    print("Starting frontend (Next.js on port 3000)...")
    frontend_proc = subprocess.Popen(
        "npm run dev",
        cwd=FRONTEND_DIR,
        shell=True,
    )
    processes.append(frontend_proc)

    vapi_updated = ngrok_url and api_key and assistant_id and update_vapi_webhook(ngrok_url, api_key, assistant_id)
    if vapi_updated:
        print("\n🚀 System is LIVE! Vapi Webhook updated automatically.\n")
    else:
        print("\nAll services running. Press Ctrl+C to stop.\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        kill_all()


if __name__ == "__main__":
    main()
